"""THE QUESTION CHOOSES ITS SEARCH: chronological recall for a ponder.

The owner, 2026-10-06: "we can have alt search engines specialized for
different lookups"; "With jev we don't even need the llm to think about the
question type or field"; and "when did I first meet x [is] a pure code lookup
that returns a span of memories that first mention x in tags, it becomes
semantically sticky when we start asking questions like 'When did I first do
x?'" -- with a complete scan of the bank ruled out on cost.

A ponder ranks by relevance, and "first" is no property of a memory's content:
it is the memory's place among all the memories that match. Asked for her very
first words, the Doctor of chat 74 pondered and got turns 15, 22, 56, 57 and
63, never turn 1 (`docs/design/DESIGN_CHRONOLOGICAL_RECALL.md` §1). So the
decision model reads the question ALONE -- the state counts as evidence, and a
question is all this needs -- and answers two choices: what the question asks
the memory for (anything; the first time; the last time; what came just
before; what came just after), and what that first or last time is OF
(meeting or seeing someone; hearing of someone or something; being somewhere;
something done, said or happening). A third, only when there is somebody to
choose: who it is about, among the people it names whom this mind knows by
name and the one who asked it. Code then runs the search built for that
question and decides the order; the model never says which came first.

THE SEARCHES, each over the rows the ponder's own net already read
(`memory_jev.memory_net`: this mind's, through `visible_memory_rows`):

- MET -- the rows that have the person in them (`memories.about`: bodies the
  mind saw in full that beat), by turn. The tag decides; only rows no tag can
  reach (a seeded past, an undated row, a bank with no row tagged with them)
  are asked whether the mind sees or meets them there.
- HEARD OF -- the first (or last) row that says the name. Code alone.
- PLACE -- the first (or last) row made there (`memories.location`). Code alone.
- Each moment code finds is asked once whether it is the one the QUESTION
  asks about; not it (the router read a question about a thing as one about
  the person asking it), and the question is walked as an ACT.
- ACT -- the rows nearest the question (by meaning and by words; within the
  person's own rows when it is about one, or the place's when it names one,
  holding their earliest or latest `RESERVE` beside the nearest `POOL`), put
  in time order and asked, in one request of at most `VERIFY_LIMIT`, whether
  the moment happens in each; the answer is the first row the model is sure
  of (`WALK_FLOOR`). A place the question names but does not ask about being at
  narrows nothing; one it asks an act at is walked too, and wins when the
  model is about as sure of its own moment.
- JUST BEFORE / JUST AFTER -- the row the model is surest shows the moment
  the question names, among the `VERIFY_LIMIT` nearest (a near tie, one moment
  told twice, to the earlier); code reads the turns on the side asked.

What comes back is the moment and the turns around it (`SPAN_TURNS`), the
moment marked (`in_time`, in the story's words: "the earliest moment I
remember with Oren Dask"), beside the ponder's own picks -- ROUTING ADDS AND
NEVER REMOVES (the research's rule: a parser that filters deletes answers). A
question read as asking for anything, a router that cannot be asked, a subject
nobody can resolve, a search that finds nothing: today's ponder, untouched.
"""

from __future__ import annotations

import re
import time

from core.db import get_setting

ORDERS = ("content", "earliest", "latest", "before", "after")
KINDS = ("met", "heard_of", "place", "act")

#: Turns a routed answer brings back: the moment's turn and the two after it
#: for a first time, the two before it and it for a last time, the moment and
#: the three on the side asked for just before / just after. Mine, named to
#: the owner, unruled.
SPAN_TURNS = 3
#: Rows a verified search asks about, in one request: its whole reach. A walk
#: takes the first this many of its candidates in time order. Mine, named,
#: unruled.
VERIFY_LIMIT = 24
#: The rows nearest the question an ACT or JUST BEFORE / AFTER search draws
#: its candidates from. Mine, named, unruled.
POOL = 40
#: The person's or the place's own earliest (or latest) rows a first- or
#: last-time walk always holds beside the nearest ones. "Her very first words"
#: are early, and the rows most like the question are the later meetings that
#: say so in as many words: measured 2026-10-06 on the Saltmere bank, the
#: meeting at turn 22 was not among the 40 Oren rows nearest "what were Oren's
#: very first words to you?" -- every one of them a later "I met Oren Dask...".
#: Mine, named, unruled.
RESERVE = 12
#: The yes-share below which a memory is not the moment: a found moment's
#: confirmation, and the surest moment a question asks what came before or
#: after (the fire itself read 0.71 for "just before the mill fire").
VERIFY_FLOOR = 0.6
#: The yes-share a first or last time must reach in a walk. Measured on the
#: Saltmere bank (2026-10-06): the first and last times themselves read
#: 0.95-0.99; the rows merely like them 0.50-0.76 -- a childhood row and an
#: ordinary visit at 0.53 and 0.55 for "the first time you lied to Ilse" (a
#: bar of 0.5 handed back the childhood), and at 0.50 and on a second asking
#: 0.64 the green lights on the river that were all "when did you first see
#: the river serpent?" (there is none) could find. Mine, named, unruled.
WALK_FLOOR = 0.8
#: Moments the model is this nearly as sure of are a tie, and a tie goes to
#: the earlier: "right after the mill fire" read the dawn after it 0.93 and
#: the fire 0.92; Tobin's confession 0.97 against an earlier scene of his at
#: the granary 0.91, which stays apart. A tie is ONE moment told twice, so
#: only rows within `TIE_REACH` turns of the surest can tie it (`_surest`).
#: Mine, named, unruled.
NEAR_TIE = 0.05
#: How many turns apart two rows can be and still be one moment told twice.
#: Replayed on 173 captured anchor decisions (2026-10-06): a reach of 3 took
#: 119 right, 1 or 2 took 111 (the mill fire and the dawn after it stand 3
#: turns apart, and the dawn reads a little surer in 8 of 13), 4 to 6 took
#: 118. Its own number, not `SPAN_TURNS` -- that one is how much a packet
#: brings back, and changing it must not move which moment is found. Mine,
#: named to the owner.
TIE_REACH = 3
#: How much of a memory a verification question carries. The ponder's grade
#: reads 500 characters (`memory_jev.MEMORY_CHARS`); a one-memory turn runs
#: ~950 at the median and ~1,800 at p90, and "What I did" comes after "What I
#: witnessed", so a check of what the mind DID needs most of the row.
VERIFY_CHARS = 1500
#: Rows within one fusion: the equal-weight RRF constant the net uses.
_K = 30

def routing_on() -> bool:
    """Whether a ponder routes its question (setting `ponder_routes`; on unless
    it is "off")."""
    return str(get_setting("ponder_routes") or "on").strip().lower() not in {"off", "0", "false", "no"}


# --- reading names in a question -------------------------------------------------------

def says_name(text, name):
    """Whether `text` names `name`, by the one rule the ponder's ABOUT lane
    reads names with (`memory_jev.named_in`)."""
    from mind.memory_jev import named_in
    return bool(named_in(text, [name]))


def names_place(text, place):
    """Whether `text` names a place: every word of its name of three letters
    or more (other than "the") stands in the text -- "the Lantern Inn" is
    named by "your first night at the Lantern Inn" and not by "the green
    lantern", which a person's rule (any one word) would take for it -- or, in
    a script written without spaces, the whole name stands in it."""
    from mind.memory_jev import _UNSPACED
    place = str(place or "").strip()
    if not place:
        return False
    folded = str(text or "").casefold()
    if _UNSPACED.search(place):
        return place.casefold() in folded
    tokens = [t for t in re.findall(r"\w+", place.casefold()) if len(t) >= 3 and t != "the"]
    words = set(re.findall(r"\w+", folded))
    return bool(tokens) and all(t in words for t in tokens)


# --- the router --------------------------------------------------------------------------

def question_state(query, asker=None):
    """The router's and the verifier's state: the question alone, and who
    asked it when somebody did. Labels are protocol, as the ponder's are
    (`memory_jev.ponder_state`)."""
    q = " ".join(str(query or "").split())
    if asker:
        return f"{asker} ASKED YOU: {q}"
    return "THE QUESTION YOU ARE ASKING YOUR OWN MEMORY: " + q


def route_questions(people, language=None, asker=None):
    """The router's questions, asked together against the question alone:
    what it asks the memory for (`route:order`); what a first or last time
    is OF (`route:kind`); whether it asks about something that already
    happened at all (`route:past`); and -- only when there is somebody to
    choose -- who it is about (`route:who`: `p<i>`, the asker labelled as
    the one asking, or `none`).

    `route:past` is its own yes/no rather than a word in the order options,
    measured 2026-10-06 on 48 English and 30 Japanese questions read by hand:
    with the order choice alone, every chronological question routed but a
    plan ("what should we do before the curfew tonight?"), a direction
    ("what comes after the toll road?") and a superlative ("the last person
    you'd trust") routed too -- 13 of 17 and 11 of 13 content questions kept;
    asked as its own question, naming what it is not (a named cause helps a
    yes/no, `docs/experiments/SUPERSEDED_LINKS_2026_10_05.md`), 17 of 17 and
    13 of 13 with every chronological question still found. The asker's
    label and the named `none` took the Japanese `who` from 8 of 17 right to
    13: without them it chose the one asking for a question about a lantern."""
    from llm.prompts import character_jev_options, character_jev_text
    qs = {"route:order": {"type": "choice", "instructions": character_jev_text("route_order", language),
                          "criteria": character_jev_options("route_order", language)},
          "route:kind": {"type": "choice", "instructions": character_jev_text("route_kind", language),
                         "criteria": character_jev_options("route_kind", language)},
          "route:past": {"type": "choice", "instructions": character_jev_text("route_past", language),
                         "criteria": character_jev_options("yesno", language)}}
    if people:
        labels = character_jev_options("route_who", language)
        criteria = {f"p{i}": (labels["asker"].replace("{name}", str(name)) if asker and name == asker
                              else str(name))
                    for i, name in enumerate(people)}
        criteria["none"] = labels["none"]
        qs["route:who"] = {"type": "choice", "instructions": character_jev_text("route_who", language),
                           "criteria": criteria}
    return qs


#: The yes-share at which a question asks about something that already
#: happened (`route:past`); below it the question is not routed.
PAST_FLOOR = 0.5


def read_route(answers, people):
    """`{"order", "kind", "who"}` from the router's answers: each the option it
    rated most likely (probabilities are uncalibrated and rarely high, so the
    ordering is read, never a threshold); "content" when the order is
    unanswered, or the question asks about nothing that already happened."""
    from mind import character_jev as jev
    order = jev.pick(answers, "route:order")
    kind = jev.pick(answers, "route:kind")
    who = jev.pick(answers, "route:who") if people else None
    person = None
    if who and who.startswith("p") and who[1:].isdigit() and int(who[1:]) < len(people):
        person = people[int(who[1:])]
    if "route:past" in answers and jev._probabilities(answers["route:past"]).get("yes", 0.0) < PAST_FLOOR:
        order = "content"
    return {"order": order if order in ORDERS else "content",
            "kind": kind if kind in KINDS else "act",
            "who": person}


def route_question(query, *, asker=None, people=(), language=None):
    """Jev's reading of one question: `{"order", "kind", "who"}`. Raises
    `decisions.DecisionError` when it cannot be asked."""
    from mind import character_jev as jev
    people = list(dict.fromkeys(str(p) for p in people if str(p or "").strip()))
    return read_route(jev.ask(question_state(query, asker), route_questions(people, language, asker)), people)


_POOL = None


def route_soon(query, *, asker=None, people=(), language=None):
    """`route_question` started on its own thread, so the router's request
    runs beside the ponder's grade rather than after it (both about a third of
    a second); the caller's context goes with it -- the frame, the story's
    language and the call ledger the request is recorded in."""
    global _POOL
    from concurrent.futures import ThreadPoolExecutor
    from contextvars import copy_context
    if _POOL is None:
        _POOL = ThreadPoolExecutor(max_workers=4, thread_name_prefix="ponder-route")
    return _POOL.submit(copy_context().run, route_question, query, asker=asker, people=people,
                        language=language)


# --- what a row is -------------------------------------------------------------------------

def _order_key(mem, newest_first=False):
    """A row's place in time: oldest first, or with `newest_first` the newest
    TURN first. An undated row counts as the oldest -- first oldest-first, last
    newest-first; a first meeting's check asks an undated row that names the
    person because it sorts first.

    WITHIN ONE TURN THE BEAT'S OWN ORDER HOLDS, whichever way the search
    walks: the moment itself, then what the mind concluded about it (a
    `kind` "inference" row, which the commit writes after the turn's episode).
    Reversing the whole order put the conclusion first, so a last time landed
    on it: "when did you last see Oren?" was marked on Mara's conclusion that
    he was not coming back, not on the sighting it was drawn from, in all three
    runs of 2026-10-06's replication; and "the last time you were inside the
    chapel" confirmed the conclusion row of the right visit (0.01) and walked
    on to the wrong one.

    ONLY A STORY BEAT HAS AN ORDER OF ITS OWN. A seeded past shares one
    pseudo-turn (`PRESTORY_TURN_IDX`) whose rows are separate moments in the
    order they were minted -- `_span` reads them so -- and newest first walks
    them newest-minted first, as any time (review, 2026-10-06: the beat's rule
    had walked a whole seeded past oldest first for a last time)."""
    turn = mem.get("turn_idx")
    when = mem.get("encoded_at_seconds") or 0.0
    written = mem.get("id") or 0
    if isinstance(turn, int) and turn >= 0:
        within = (mem.get("kind") == "inference", written)
    else:
        within = (False, -written if newest_first else written)
    if newest_first:
        return (turn is None, -(turn if turn is not None else 0), -when) + within
    return (turn if turn is not None else -10 ** 9, when) + within


def _in_time(mems, newest_first=False):
    """`mems` in time order (`_order_key`)."""
    return sorted(mems, key=lambda m: _order_key(m, newest_first))


def _text_of(mem):
    return " ".join(str(mem.get(k) or "") for k in ("content", "gist"))


def _tagged(mem, person):
    want = str(person or "").casefold()
    return bool(want) and any(str(t).casefold() == want for t in mem.get("about") or [])


def _line(mem, current_turn_idx, known=()):
    """One memory as a verification question carries it: the ponder grade's
    line (`memory_jev.memory_line`, who was in it included) with more of the
    row (`VERIFY_CHARS`) -- passed, never set on the module, since minds
    decide on parallel threads and another's grade reads that length."""
    from mind.memory_jev import memory_line
    return memory_line(mem, current_turn_idx, known, chars=VERIFY_CHARS)


# --- the searches ---------------------------------------------------------------------------

def _fused(lanes, among=None):
    """Ids by equal-weight RRF over `lanes` (each a ranking of ids), only those
    `among` when given."""
    score = {}
    for ranking in lanes:
        rank = 0
        for mid in ranking:
            if among is not None and mid not in among:
                continue
            rank += 1
            score[mid] = score.get(mid, 0.0) + 1.0 / (_K + rank)
    return sorted(score, key=lambda mid: (-score[mid], mid))


def _subject_lane(memories, vectors, ids, query, person, embedded):
    """The subject's own rows ranked by meaning against the question with the
    name said as "them" (`memory_jev.without_names`): the rows share the
    person, and the name only pulls the query toward everything with them."""
    from mind.memory_common import _cos
    from mind.memory_jev import without_names
    if embedded is None or getattr(embedded, "fallback", False):
        return []
    aimed = embedded.vectors[0]
    if person:
        try:
            from llm.providers import embed_texts_meta
            other = embed_texts_meta([without_names(query, [person])])
            if (not getattr(other, "fallback", False) and other.model_key == embedded.model_key
                    and other.dimensions == embedded.dimensions):
                aimed = other.vectors[0]
        except Exception:  # noqa: BLE001 -- the lane falls back to the question as asked
            pass
    score = {}
    for mid in ids:
        fv, cv = vectors.get(mid) or (None, None)
        score[mid] = max(_cos(aimed, fv) if fv is not None else 0.0,
                         _cos(aimed, cv) if cv is not None else 0.0)
    return sorted(ids, key=lambda mid: (-score[mid], mid))


def _yes_shares(rows, question, state, current_turn_idx, known, language, record, **fill):
    """How surely the decision model says yes, for each of `rows` -- one
    request, every row its own question against the question alone."""
    from llm.prompts import character_jev_options, character_jev_text
    from mind import character_jev as jev
    from mind.affect_appraisal import _fill
    if not rows:
        return []
    yesno = character_jev_options("yesno", language)
    text = character_jev_text(question, language)
    qs = {f"moment:{i}": {"type": "choice",
                          "instructions": _fill(text, {**fill, "memory": _line(m, current_turn_idx, known)}),
                          "criteria": dict(yesno)}
          for i, m in enumerate(rows)}
    answers = jev.ask(state, qs)
    record["verified"] = record.get("verified", 0) + len(qs)
    return [jev._probabilities(answers.get(f"moment:{i}")).get("yes", 0.0) for i in range(len(rows))]


def _first_sure(rows, shares, floor=None):
    """The first of `rows` (in the order walked) the model is sure shows the
    moment (`floor`, a walk's `WALK_FLOOR` by default); None when it is sure
    of none. The first, never the surest: a plainer first time reads a little
    lower than a later one that says it outright, and the order is the
    question."""
    floor = WALK_FLOOR if floor is None else floor
    return next((row for row, p in zip(rows, shares) if p >= floor), None)


def _near(row, other):
    """Both rows in the story's turns, `TIE_REACH` or fewer apart -- the
    STORY's turns, not this mind's own as `_span` counts them: a mind with no
    rows between two moments a month apart must not read them as one (the
    chest and the mill fire, below). The reverse -- one moment retold after
    beats the mind was not there for -- is open: story time would tell both
    apart, with a window the owner has not named (`UNBUILT_CHARACTERS.md`)."""
    a, b = row.get("turn_idx"), other.get("turn_idx")
    return (isinstance(a, int) and isinstance(b, int) and a >= 0 and b >= 0
            and abs(a - b) <= TIE_REACH)


def _surest(rows, shares):
    """`(row, share)` for the row the model is surest shows the moment -- the
    earliest of those within `NEAR_TIE` of it that stand within `TIE_REACH`
    turns of it (`_near`); `(None, 0.0)` when it is sure of none.

    A TIE IS ONE MOMENT TOLD TWICE, never two moments. The rule was made for
    the fire and the dawn after it, three turns apart; with no reach it handed
    "right after you carried Ilse's chest up to the chapel house" (0.97) to the
    mill-fire night 128 turns earlier (0.94), in every run of 2026-10-06's
    replication. Replayed on the 52 captured anchor decisions, the reach took
    the right moments from 31 to 35 and the wrong from 21 to 17, and moved no
    right one. A seeded or undated row ties nothing but itself; rows the model
    reads exactly alike at the top go to the earlier, as before (one or two
    decimals make that common)."""
    if not rows or max(shares) < VERIFY_FLOOR:
        return None, 0.0
    top = max(shares)
    surest = min((i for i in range(len(rows)) if shares[i] == top), key=lambda i: _order_key(rows[i]))
    tied = [i for i in range(len(rows))
            if shares[i] >= top - NEAR_TIE and (i == surest or _near(rows[i], rows[surest]))]
    best = min(tied, key=lambda i: _order_key(rows[i]))
    return rows[best], shares[best]


def _span(memories, anchor, before, after):
    """The anchor's turn and `before`/`after` turns either side, every row of
    this mind's in them, oldest first. A seeded past (turn below zero) or an
    undated row counts in single rows formed beside it, as `expand` does."""
    rows = sorted(memories.values(), key=_order_key)
    turn = anchor.get("turn_idx")
    if turn is None or turn < 0:
        same = [m for m in rows if m.get("turn_idx") == turn]
        at = next((i for i, m in enumerate(same) if m.get("id") == anchor.get("id")), 0)
        return same[max(0, at - before):at + after + 1]
    turns = sorted({m["turn_idx"] for m in rows if m.get("turn_idx") is not None and m["turn_idx"] >= 0})
    at = turns.index(turn)
    keep = set(turns[max(0, at - before):at + after + 1])
    return [m for m in rows if m.get("turn_idx") in keep]


def answer(route, query, *, memories, vectors, lanes, embedded, known, places,
           current_turn_idx, language=None, asker=None, record=None):
    """The rows a routed question brings back, the moment first and marked
    (`in_time`), then the turns around it in time order; `[]` when the route
    asks for anything or the search finds nothing. Never raises past a
    `decisions.DecisionError` from a verification request."""
    record = record if record is not None else {}
    order, kind, person = route.get("order"), route.get("kind"), route.get("who")
    if order not in ("earliest", "latest", "before", "after") or not memories:
        return []
    named = [p for p in places if names_place(query, p)]
    place = max(named, key=len) if named else None
    state = question_state(query, asker)
    walk_back = order == "latest"
    rows = _in_time(memories.values(), newest_first=walk_back)
    first_or_last = order in ("earliest", "latest")
    anchor, how = None, ""

    found = []        # moments code found, in the order to try them
    if first_or_last and kind == "met" and person:
        # THE TAG DECIDES who a moment had in it (`memories.about`: the bodies
        # the mind saw in full). For a FIRST meeting the rows before the first
        # tagged one that say the name are asked whether the mind sees or
        # meets them there -- a seeded past no tag can reach, an older bank,
        # and a first meeting the mind only heard (a tag is sight alone). For
        # a LAST one nothing after the last tag is asked: a row where Oren was
        # talked about after he left read as "you see him here" to the
        # decision model (2026-10-06).
        tagged = [m for m in rows if _tagged(m, person)]
        cut = rows.index(tagged[0]) if tagged else len(rows)
        before_tag = [m for m in rows[:cut] if says_name(_text_of(m), person)
                      and (not walk_back or not tagged or m.get("turn_idx") is None or m["turn_idx"] < 0)]
        before_tag = before_tag[:VERIFY_LIMIT]
        if before_tag:
            # Whether a person is THERE is a plainer question than whether a
            # moment happens, so it is read at the confirmation's floor, not a
            # walk's: "how long have you known Ilse?" lost her seeded rescue
            # from the ice to the walk's (2026-10-06).
            met = _first_sure(before_tag, _yes_shares(before_tag, "memory_met", state, current_turn_idx,
                                                      known, language, record, person=person),
                              floor=VERIFY_FLOOR)
            found.append(met)
        found.append(tagged[0] if tagged else None)
        how = "with"
    elif first_or_last and kind == "heard_of" and person:
        found.append(next((m for m in rows if says_name(_text_of(m), person)), None))
        how = "named"
    elif first_or_last and kind == "place" and place:
        want = place.casefold()
        found.append(next((m for m in rows if str(m.get("location") or "").strip().casefold() == want), None))
        how = "at"
    for candidate in dict.fromkeys(m["id"] for m in found if m is not None):
        # A MOMENT CODE FOUND IS ASKED WHETHER IT IS THE ONE ASKED ABOUT, each
        # in turn: the router can read a question about a thing as one about
        # the person asking it ("when did you first see the river serpent?"
        # came back as meeting Wren, and her arrival at turn 1 is certainly the
        # first row with her in it). None is it, and the question is walked as
        # any other -- the person kept: the walk keeps to a person only where
        # the question names them, which is what the one asking needs, and
        # dropping them sent "the night I first met Hinami -- her very first
        # words" walking the whole bank once her first tagged row (the Doctor
        # landing beside her, no words yet) was rightly refused, so her first
        # words a turn later never reached the walk (chat 74, 2026-10-06).
        # Asked as the walk for its kind asks: a first-heard row is one in
        # which the subject is only talked about, which `memory_moment` sets
        # aside; `memory_heard` still asks about what the QUESTION asks about,
        # so a misread route is refused all the same.
        row = memories[candidate]
        confirmed = _yes_shares([row], "memory_heard" if how == "named" else "memory_moment", state,
                                current_turn_idx, known, language, record)
        record["confirmed"] = round(confirmed[0], 3)
        if confirmed[0] >= VERIFY_FLOOR:
            anchor = row
            record["anchor_p"] = round(confirmed[0], 3)
            break
    if anchor is None:
        how = ""
    if anchor is None:
        # THE WALK: the rows nearest the question in time order, the first the
        # model is sure shows the moment taken (`_first_sure`). For a
        # first or last time it is narrowed to the person's own rows when the
        # question is about one, or the place's when it names one, and holds
        # their earliest (or latest) `RESERVE` beside the nearest. The moment a
        # question asks what came before or after is looked for among them all
        # -- who the router took it to be about is no reason to drop the
        # moment itself (it read the one asking for "what did you do right
        # after Tobin told you about the grain?", 2026-10-06, and Tobin's
        # confession had no asker in it) -- and is the row the model is
        # SUREST shows it, not the first it is sure of: an earlier moment
        # merely like it is not it.
        # NARROWED ONLY BY WHAT THE QUESTION SAYS. A person, when the question
        # names them -- never the one asking because the router chose them:
        # "when did you first light the green lantern?" came back as about
        # Wren, and Mara lit it alone. A place, only when the question asks
        # about being there: "when did you last fix the Heron's rudder?" names
        # the ferry Mara stands on as a place, and the repair was ashore.
        by_person = bool(first_or_last and person and says_name(query, person))

        def ranked_among(subject):
            among = {m["id"] for m in subject} if subject is not None else set(memories)
            ranked = _fused([lanes.get("semantic") or [], lanes.get("cue") or [], lanes.get("keyword") or [],
                             _subject_lane(memories, vectors, list(among), query, person, embedded)
                             if by_person and subject is not None else []],
                            among=among)
            return ranked or sorted(among)

        def walk(subject):
            # THE HELD ROWS AND THE `POOL` NEAREST, IN TIME ORDER, CUT TO THE
            # FIRST `VERIFY_LIMIT`. Every cut drops a kind of answer, and this
            # one drops the least that matters (measured 2026-10-06, three runs
            # each on the Saltmere bench): it never reaches a first time late in
            # the story ("when did you first hear about the Moth?" asked turns
            # 27-208 while the rows naming the barge, 288 on, waited outside).
            # Cutting by nearness instead lost a plain first time that ranks
            # below later rows saying it outright (the lie to Ilse at 96, every
            # run); asking every candidate found the Moth but walked on past
            # unsure answers into false ones -- "when did you first see the river
            # serpent?" (there is none) marked a row at 0.83-0.87, "your last
            # night run for Oren" one 180 turns early -- two wrong marks for one
            # right, and a wrong mark points a mind away from what it holds.
            held = [m["id"] for m in subject[:RESERVE]] if subject else []
            pool = _in_time((memories[mid] for mid in dict.fromkeys(held + ranked_among(subject)[:POOL])),
                            newest_first=walk_back)[:VERIFY_LIMIT]
            record.setdefault("asked_turns", []).append([m.get("turn_idx") for m in pool])
            question = "memory_heard" if kind == "heard_of" else "memory_moment"
            shares = _yes_shares(pool, question, state, current_turn_idx, known, language, record)
            # A CONCLUSION IS NEVER THE MOMENT. A row of `kind` "inference" is
            # what the mind concluded, not anything done, said or seen, and
            # the check still says yes to one now and then: "what were the
            # last words you said to Oren?" walked newest first past his
            # departure (0.72-0.78) to Mara's conclusion that he was not coming
            # back (0.81-0.88) in all three runs, never reaching the words at
            # 0.98 (2026-10-06). Asked, kept with its turn's span, never taken.
            # Replayed on the captured walks: the words found in 4 of 5, a
            # wrong mark of the first missing bread gone, no right one lost.
            found = _first_sure(pool, [0.0 if m.get("kind") == "inference" else p
                                       for m, p in zip(pool, shares)])
            return found, (shares[pool.index(found)] if found is not None else 0.0)

        def made_at(where):
            want = where.casefold()
            return [m for m in rows if str(m.get("location") or "").strip().casefold() == want]

        if first_or_last:
            if by_person:
                anchor, sure = walk([m for m in rows if _tagged(m, person) or says_name(_text_of(m), person)])
            elif place and kind == "place":
                anchor, sure = walk(made_at(place))
            else:
                anchor, sure = walk(None)
                if place:
                    # A PLACE THE QUESTION NAMES, ASKED ABOUT AS AN ACT: the
                    # first night AT the inn is a moment there, and a row
                    # elsewhere merely about the inn read 0.95 for it (Wren
                    # coming out of it "full", 2026-10-06) beside the night
                    # itself at 0.98. Walked among the rows made there too,
                    # and the place's own moment taken when the model is about
                    # as sure of it -- never when the place is only named
                    # ("the Heron's rudder": nothing aboard read near the
                    # repair made ashore).
                    # And never against the order asked: both sure, the
                    # place's own moment wins when it comes on the right side
                    # of the other (earlier, for a first time) -- order
                    # decides between sure moments, as in any walk -- or,
                    # about as sure, when the other only names the place
                    # without being made there. (The residual, in
                    # UNBUILT_CHARACTERS: a first sight of a place from
                    # elsewhere that names it is such a row too.)
                    there, sure_there = walk(made_at(place))
                    # "Ahead" in the walk's own order -- newest first for a last
                    # time, so a turn's moment comes before its conclusion
                    # either way (`_order_key`).
                    ahead = (there is not None and anchor is not None
                             and _order_key(there, walk_back) < _order_key(anchor, walk_back))
                    named_only = (anchor is not None and names_place(_text_of(anchor), place)
                                  and str(anchor.get("location") or "").strip().casefold() != place.casefold())
                    if there is not None and (anchor is None or ahead
                                              or (named_only and sure_there >= sure - NEAR_TIE)):
                        anchor, sure = there, sure_there
            # "it", never "being at": a walk finds the first moment the model
            # confirms, which need not be the first row made there.
            how = "it"
        else:
            pool = [memories[mid] for mid in ranked_among(None)[:VERIFY_LIMIT]]
            anchor, sure = _surest(pool, _yes_shares(pool, "memory_anchor", state, current_turn_idx, known,
                                                     language, record))
            how = "moment"
        if anchor is not None:
            record["anchor_p"] = round(sure, 3)
    if anchor is None:
        record.update(found=False)
        return []
    before, after = {"earliest": (0, SPAN_TURNS - 1), "latest": (SPAN_TURNS - 1, 0),
                     "before": (SPAN_TURNS, 0), "after": (0, SPAN_TURNS)}[order]
    span = _span(memories, anchor, before, after)
    # The mark names what it was found by: the place on the place path, where
    # a person the router also picked would read "being at Oren Dask".
    subject = place if how == "at" else (person or place)
    marked = dict(anchor, in_time=in_time_text(order, how, subject, language), picked_by="route")
    out = [marked] + [dict(m, picked_by="route") for m in span if m.get("id") != anchor.get("id")]
    record.update(found=True, anchor_turn=anchor.get("turn_idx"), span=len(out), subject=subject or "")
    return out


def in_time_text(order, how, subject, language=None):
    """The words the found moment is marked with, in the story's language
    (`character_tools.in_time_<order>_<how>`)."""
    from llm.prompts import character_tools_text
    if order in ("before", "after"):
        key = f"in_time_{order}"
    else:
        side = "first" if order == "earliest" else "last"
        key = f"in_time_{side}_{how if subject or how == 'it' else 'it'}"
    text = character_tools_text(key, language)
    return text.replace("{subject}", str(subject or ""))


def routed_ponder(query, *, asker, people, places, memories, vectors, lanes, embedded, known,
                  current_turn_idx, language=None, record=None):
    """Route one question and answer it: `(rows, route)`. The router and the
    search both fail open to `[]` -- the ponder's own picks still stand."""
    record = record if record is not None else {}
    t0 = time.time()
    try:
        route = route_question(query, asker=asker, people=people, language=language)
    except Exception as exc:  # noqa: BLE001 -- the floor: today's ponder
        record.update(unasked=f"{type(exc).__name__}: {str(exc)[:200]}", seconds=round(time.time() - t0, 3))
        return [], None
    record.update(route)
    try:
        rows = answer(route, query, memories=memories, vectors=vectors, lanes=lanes, embedded=embedded,
                      known=known, places=places, current_turn_idx=current_turn_idx, language=language,
                      asker=asker, record=record)
    except Exception as exc:  # noqa: BLE001 -- a search that cannot finish adds nothing
        record.update(failed=f"{type(exc).__name__}: {str(exc)[:200]}")
        rows = []
    record.update(seconds=round(time.time() - t0, 3))
    return rows, route
