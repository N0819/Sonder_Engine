"""Research for the Writers' Room: the web, read under a mandate, disclosed
in the thread, cached per story, and usable in the world only as filed lore.

WHY IT EXISTS. The Story Planner is a coding agent over a world, and a coding
agent's best tool after the codebase is the reference shelf: what a
fourteenth-century tannery district smelled like, how a harbourmaster's
ledger was kept, what a real street looks like where a story is set. The
Charter Planner shaping a town wants the same. The Dramaturge does not get
it (owner, 2026-09-03): its value is what it proposes from craft and the
story it is watching, and a search would have it hunting for somebody
else's plot.

FOUR CONDITIONS, each answering a way this could become a second source of
truth or a leak of the story off the machine:

* THE GRANT. Both tools refuse unless a standing mandate carries the
  `research` capability (`RESEARCH_CAPABILITY`). Off by default; a story
  starts with no mandate at all (`story/mandates.py`). The vocabulary the
  grant is checked against is `story.mandates.MANDATE_CAPABILITIES`, read
  at call time; when the vocabulary lacks the word, the refusal says so.
* THE DISCLOSURE. Every query and every page address is written into the
  room thread as a `room` notice BEFORE it leaves the machine, so the
  player reads exactly what was sent. A local-first engine does not ship a
  story's particulars to a search provider in silence.
* THE CACHE. Results are cached per story under the `room_research` world
  key -- frame-AGNOSTIC, because the web is not the story: a rewind does
  not unsay a fact about the world outside, and a branch that asked the
  same question deserves the same answer without a second request. A
  cache row carries its fetch date, so a replay reads the row and never
  the web, and a `CACHE_TTL_DAYS`-old row is refetched.
* THE FILING. A result is REFERENCE, not a fact of the world, until it is
  filed as lore through a package's `file_lore` operation with the
  `web_reference` disposition (`WEB_REFERENCE_DISPOSITION`) and the address
  and date in its provenance note. The tools return each result with a
  ready `as_lore` template for exactly that operation and nothing else;
  there is no path from a search result into a plan, a room or a mind.

Budgets are per BEAT (the story's turn index at the time of the call),
because a tool has no notion of which reply it is serving; a reply that
spans no beat shares the beat's budget with the next reply in the same
beat. Every cap is named below.
"""

from __future__ import annotations

import hashlib
import time

from core.db import wget, wset

#: The mandate capability both tools require. Added to
#: `story.mandates.MANDATE_CAPABILITIES` by the fork that owns that table;
#: until it is there, nothing can grant it and both tools refuse.
RESEARCH_CAPABILITY = "research"

#: The provenance disposition a filed result carries. Belongs in
#: `mind/canon_provenance.ADJUDICATED_DISPOSITIONS` (that module's owner
#: wires it); the `as_lore` template names it so the filing can carry it.
WEB_REFERENCE_DISPOSITION = "web_reference"

#: Searches allowed per beat (see the module docstring for why per beat).
SEARCHES_PER_BEAT = 6
#: Pages fetched per beat.
FETCHES_PER_BEAT = 4
#: Results returned per search: the default and the most a call may ask.
RESULTS_PER_SEARCH = 5
RESULTS_PER_SEARCH_CAP = 8
#: Characters kept of one result's snippet.
RESULT_CHARS = 600
#: Characters kept of one fetched page's text.
PAGE_CHARS = 6000
#: Total characters of web text one beat may take in, searches and pages
#: together; past it the next call is refused until the next beat.
INGEST_CHARS_PER_BEAT = 30_000
#: A cached answer older than this is fetched again.
CACHE_TTL_DAYS = 30
#: Cached searches and cached pages kept per story, each; oldest fall off.
CACHE_ROWS_CAP = 200
#: Beats of budget ledger kept; older beats fall off.
LEDGER_BEATS_KEPT = 64

#: The world key. NOT in `FRAME_SCOPED_WORLD_KEYS`, deliberately.
RESEARCH_CACHE_KEY = "room_research"

#: The tool names, for an agent's manifest filter: the Story Planner and the
#: Charter Planner are handed these; the Dramaturge is not (owner, 2026-09-03).
RESEARCH_TOOL_NAMES = ("web_search", "fetch_page")

#: The thread notices, written before the request leaves. Fixed prefixes,
#: so the catalog can carry them; the query itself follows the colon.
SEARCH_NOTICE = "Searched the web for"
FETCH_NOTICE = "Read the page"


def _now():
    return time.time()


def _text(value, limit):
    return " ".join(str(value or "").split())[:limit]


def _digest(kind, subject):
    return "%s:%s" % (kind, hashlib.sha256(
        subject.casefold().encode("utf-8")).hexdigest()[:16])


def _load(cid):
    store = wget(cid, RESEARCH_CACHE_KEY, {}) or {}
    if not isinstance(store, dict):
        store = {}
    store.setdefault("searches", {})
    store.setdefault("pages", {})
    store.setdefault("ledger", {})
    return store


def _save(cid, store):
    for section in ("searches", "pages"):
        rows = store.get(section) or {}
        if len(rows) > CACHE_ROWS_CAP:
            oldest = sorted(rows.items(), key=lambda kv: kv[1].get("fetched_at", 0))
            for key, _row in oldest[:len(rows) - CACHE_ROWS_CAP]:
                rows.pop(key, None)
    ledger = store.get("ledger") or {}
    if len(ledger) > LEDGER_BEATS_KEPT:
        for key in sorted(ledger, key=lambda k: int(k))[:len(ledger) - LEDGER_BEATS_KEPT]:
            ledger.pop(key, None)
    wset(cid, RESEARCH_CACHE_KEY, store)


def _fresh(row):
    return (_now() - float(row.get("fetched_at") or 0)) < CACHE_TTL_DAYS * 86400


def _beat(cid):
    from story.room_conversation import current_turn_idx
    return str(int(current_turn_idx(cid) or 0))


# ---------------------------------------------------------------------------
# The gate and the budget
# ---------------------------------------------------------------------------

def require_grant(cid, frame_id):
    """Refuse unless a standing mandate permits research. Returns the
    coverage row (the mandates cited) for the caller to report."""
    from story import mandates
    if RESEARCH_CAPABILITY not in mandates.MANDATE_CAPABILITIES:
        raise ValueError(
            "the room's mandate vocabulary has no research capability; "
            "nothing can grant the web until it is added")
    cov = mandates.coverage(cid, frame_id, [RESEARCH_CAPABILITY])
    if not cov["ok"]:
        raise ValueError(
            "no standing mandate permits research: ask the player to allow "
            "the room to read the web, and say what for")
    return cov


def budget_left(cid):
    """What this beat may still spend: `{searches, fetches, chars}`."""
    store = _load(cid)
    spent = store["ledger"].get(_beat(cid)) or {}
    return {"searches": SEARCHES_PER_BEAT - int(spent.get("searches") or 0),
            "fetches": FETCHES_PER_BEAT - int(spent.get("fetches") or 0),
            "chars": INGEST_CHARS_PER_BEAT - int(spent.get("chars") or 0)}


def _spend(store, cid, *, searches=0, fetches=0, chars=0):
    beat = _beat(cid)
    row = store["ledger"].setdefault(beat, {"searches": 0, "fetches": 0, "chars": 0})
    row["searches"] += searches
    row["fetches"] += fetches
    row["chars"] += chars


def _disclose(cid, frame_id, prefix, subject):
    """The notice in the thread, written BEFORE the request leaves."""
    from story.room_conversation import add_message, current_turn_idx
    add_message(cid, frame_id, "room", "%s: %s" % (prefix, subject),
                turn_idx=current_turn_idx(cid))


# ---------------------------------------------------------------------------
# The filing template
# ---------------------------------------------------------------------------

def as_lore(*, url, title, content_from, fetched_at, subject_id=""):
    """The one shape a result may take into the world: a `file_lore`
    operation carrying the address and date as provenance. `subject_id` is
    the room's to fill (a room id, a plan uid, a charter key, or an id-shaped
    slug for a setting fact); `content` is the result's own text, named by
    `content_from` rather than copied, so a result is not carried twice;
    `disposition` is `web_reference`."""
    date = time.strftime("%Y-%m-%d", time.gmtime(float(fetched_at or _now())))
    return {
        "op": "file_lore",
        "subject_id": subject_id,
        "subject_kind": "setting",
        "title": _text(title, 200),
        "content_from": content_from,
        "category": "other",
        "disposition": WEB_REFERENCE_DISPOSITION,
        "source_url": url,
        "fetched_at": date,
        "provenance": "%s %s fetched %s" % (WEB_REFERENCE_DISPOSITION, url, date),
    }


# ---------------------------------------------------------------------------
# The tools
# ---------------------------------------------------------------------------

def web_search(cid, frame_id, *, query, k=None):
    """Search the web for a subject the story's lore does not hold.

    Refused without a research mandate, past the beat's budget, or with no
    provider configured. Disclosed in the thread first. Cached per story
    and query for `CACHE_TTL_DAYS`. Returns
    ``{query, results: [{title, url, snippet, fetched_at, as_lore}], cached,
    cited, budget}``.
    """
    from llm import research_providers as rp

    cov = require_grant(cid, frame_id)
    query = _text(query, 300)
    if not query:
        raise ValueError("a search needs a query")
    try:
        k = int(k) if k is not None else RESULTS_PER_SEARCH
    except (TypeError, ValueError):
        k = RESULTS_PER_SEARCH
    k = max(1, min(RESULTS_PER_SEARCH_CAP, k))

    store = _load(cid)
    key = _digest("search", query)
    row = store["searches"].get(key)
    if row and _fresh(row):
        results = list(row["results"])[:k]
        return {"query": query, "results": _with_templates(results),
                "cached": True, "fetched_at": row["fetched_at"],
                "cited": cov["cited"], "budget": budget_left(cid)}

    left = budget_left(cid)
    if left["searches"] <= 0:
        raise ValueError("this beat's research budget is spent: no more searches "
                         "until the story moves")
    if left["chars"] <= 0:
        raise ValueError("this beat's research budget is spent: nothing more can "
                         "be read until the story moves")
    if rp.configured() is None:
        raise ValueError("no research provider configured")

    _disclose(cid, frame_id, SEARCH_NOTICE, query)
    try:
        hits = rp.search(query, k)
    except rp.ResearchError as exc:
        raise ValueError("the web could not be searched: %s" % exc)
    fetched_at = _now()
    results = []
    for hit in hits:
        results.append({"title": _text(hit.get("title"), 200),
                        "url": str(hit.get("url") or ""),
                        "snippet": _text(hit.get("snippet"), RESULT_CHARS),
                        "fetched_at": fetched_at})
    chars = sum(len(r["snippet"]) for r in results)
    store = _load(cid)
    store["searches"][key] = {"query": query, "results": results,
                              "fetched_at": fetched_at,
                              "provider": (rp.configured() or {}).get("provider")}
    _spend(store, cid, searches=1, chars=chars)
    _save(cid, store)
    return {"query": query, "results": _with_templates(results), "cached": False,
            "fetched_at": fetched_at, "cited": cov["cited"],
            "budget": budget_left(cid)}


def fetch_page(cid, frame_id, *, url):
    """Read one page the search returned, as text. Same gate, disclosure,
    cache and budget as `web_search`. Returns ``{url, title, text,
    fetched_at, cached, cited, as_lore, budget}``."""
    from llm import research_providers as rp

    cov = require_grant(cid, frame_id)
    url = _text(url, 2000)
    if not url:
        raise ValueError("a page needs an address")

    store = _load(cid)
    key = _digest("page", url)
    row = store["pages"].get(key)
    if row and _fresh(row):
        return {"url": row["url"], "title": row["title"], "text": row["text"],
                "fetched_at": row["fetched_at"], "cached": True,
                "cited": cov["cited"], "budget": budget_left(cid),
                "as_lore": as_lore(url=row["url"], title=row["title"],
                                   content_from="text", fetched_at=row["fetched_at"])}

    left = budget_left(cid)
    if left["fetches"] <= 0:
        raise ValueError("this beat's research budget is spent: no more pages "
                         "until the story moves")
    if left["chars"] <= 0:
        raise ValueError("this beat's research budget is spent: nothing more can "
                         "be read until the story moves")
    if rp.configured() is None:
        raise ValueError("no research provider configured")

    _disclose(cid, frame_id, FETCH_NOTICE, url)
    try:
        page = rp.fetch(url)
    except rp.ResearchError as exc:
        raise ValueError("the page could not be read: %s" % exc)
    fetched_at = _now()
    text = _text(page.get("text"), min(PAGE_CHARS, max(0, left["chars"])))
    title = _text(page.get("title"), 200)
    store = _load(cid)
    store["pages"][key] = {"url": page.get("url") or url, "title": title,
                           "text": text, "fetched_at": fetched_at}
    _spend(store, cid, fetches=1, chars=len(text))
    _save(cid, store)
    return {"url": page.get("url") or url, "title": title, "text": text,
            "fetched_at": fetched_at, "cached": False, "cited": cov["cited"],
            "budget": budget_left(cid),
            "as_lore": as_lore(url=page.get("url") or url, title=title,
                               content_from="text", fetched_at=fetched_at)}


def _with_templates(results):
    out = []
    for r in results:
        row = dict(r)
        row["as_lore"] = as_lore(url=r["url"], title=r["title"],
                                 content_from="snippet", fetched_at=r["fetched_at"])
        out.append(row)
    return out


# ---------------------------------------------------------------------------
# The tool table entries (appended to `story.room_tools.TOOLS`)
# ---------------------------------------------------------------------------

def tool_entries(schema):
    """The two entries, built with the caller's `_schema` helper so they
    match the table's shape exactly."""
    _S, _I = {"type": "string"}, {"type": "integer"}
    return [
        {"name": "web_search",
         "description": (
             "Search the web for reference material the story's lore does not "
             "hold -- how a real trade, place, period or practice worked. Only "
             "under a standing mandate that permits research; the query is "
             "written into the room thread before it is sent, so the player "
             "sees what left the machine. Results are REFERENCE, not facts of "
             "the world: nothing here may be planned on until it is filed "
             "through a package as lore, and each result carries an `as_lore` "
             "template (a file_lore operation with the address and date as "
             "provenance) for exactly that. Cached per story; a repeat reads "
             "the cache. Budgeted per beat."),
         "args": schema({"query": _S, "k": _I}, ["query"]),
         "handler": web_search, "long": True},
        {"name": "fetch_page",
         "description": (
             "Read one page a search returned, as text, under the same mandate, "
             "disclosure, cache and budget as web_search. The text is reference "
             "until filed through a package as lore; the result carries the "
             "`as_lore` template."),
         "args": schema({"url": _S}, ["url"]),
         "handler": fetch_page, "long": True},
    ]
