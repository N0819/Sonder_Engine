#!/usr/bin/env python3
"""Which mechanisms actually fire, and out of how many chances.

Four mechanisms in this engine were built, documented, tested, and never ran
once in production -- `initial_parallel_reactors`, `BehaviorController`,
`ActionStage`, and (as this tool's first run showed) `memory_disputes`. None of
them was visible as dead from reading the code, because reading the code tells
you what CAN happen. Three of them were found only because somebody went
looking by hand, one query at a time.

The rule this encodes: **no mechanism should be enriched before its fire rate
is known.** Enriching something that never runs is how a system grows machinery
nobody can observe.

THE DENOMINATOR IS THE WHOLE POINT. `memory_disputes` measured against every
memory row reads 0 of 6,460 -- a number that sounds like a catastrophe and
means almost nothing, because the field did not exist for most of that corpus.
Measured against the beats that could actually have carried one it reads 0 of
178, next to a sibling field introduced in the same commit that fires 78% of
the time. That second pair of numbers is a diagnosis; the first is noise. So
every mechanism here declares what its own opportunity is, and a mechanism
whose opportunity count is zero reports `no chances` rather than 0%.

    python3 tools/fire_rates.py                  # whole corpus
    python3 tools/fire_rates.py --last 50        # last 50 turns of each chat
    python3 tools/fire_rates.py --chat 59        # one story
    python3 tools/fire_rates.py --json           # for diffing across releases

Read-only. Never opens the database for writing and never imports the engine,
so it is safe to run against a live `engine.db` while the server is up.
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from collections import Counter, defaultdict

# Steps whose active variant carries per-mind character results.
CHARACTER_STEPS = ("interaction_loop", "reaction_loop")

# Fields on a character result. The value is what counts as having fired; the
# key's PRESENCE is what counts as a chance, because these arrived at different
# times and an older result never had the option.
RESULT_FIELDS = [
    ("memory_disputes", "a memory this mind now reads differently"),
    ("remember_lines", "a line from this beat worth keeping"),
    ("memory_effects", "what recalled material actually did"),
    ("belief_updates", "a belief formed or revised"),
    ("association_updates", "a learned cue->response link"),
    ("mind_model_updates", "a hypothesis about another mind"),
    ("relationship_updates", "stance toward someone moved"),
    ("intent_ops", "an intention formed, advanced or dropped"),
    ("manifest", "interior state surfaced into conduct"),
    ("unbidden_probe", "an unbidden memory was evaluated"),
    ("memory_evidence_used", "a past row cited as evidence"),
    ("present_evidence_used", "this beat cited as evidence"),
]


def _empty(value) -> bool:
    return value is None or value == "" or value == [] or value == {}


class Row:
    """One measured mechanism."""

    def __init__(self, layer, name, fired, chances, note=""):
        self.layer = layer
        self.name = name
        self.fired = fired
        self.chances = chances
        self.note = note

    @property
    def rate(self):
        return (self.fired / self.chances) if self.chances else None

    def as_dict(self):
        return {"layer": self.layer, "name": self.name, "fired": self.fired,
                "chances": self.chances, "rate": self.rate, "note": self.note}


def connect(path):
    if not os.path.exists(path):
        sys.exit(f"no database at {path}")
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    return con


def turn_scope(con, chat=None, last=None):
    """The turn ids in scope, and the chat ids they belong to.

    `--last N` is per chat rather than global: a corpus with one 400-turn story
    and twenty 3-turn ones would otherwise report "the last 50 turns" as fifty
    turns of a single story.
    """
    where, params = "", []
    if chat is not None:
        where, params = "WHERE chat_id=?", [chat]
    rows = con.execute(
        f"SELECT id, chat_id, idx FROM turns {where} ORDER BY chat_id, idx",
        params).fetchall()
    if last:
        by_chat = defaultdict(list)
        for r in rows:
            by_chat[r["chat_id"]].append(r)
        rows = [r for group in by_chat.values() for r in group[-last:]]
    return [r["id"] for r in rows], sorted({r["chat_id"] for r in rows})


def _in(ids):
    """A literal IN list. The ids are integers straight out of the database,
    never user input."""
    return "(" + ",".join(str(int(i)) for i in ids) + ")" if ids else "(NULL)"


# --------------------------------------------------------------- memory bank

def memory_rows(con, turn_ids, chat_ids):
    """Mechanisms that leave their mark on the memory row itself.

    The chance is a stored memory, except where a column arrived late -- then
    the chance is a row from a bank that has the column populated at all, which
    is what separates "never fires" from "did not exist yet".
    """
    if not chat_ids:
        return []
    scope = f"WHERE chat_id IN {_in(chat_ids)}"
    if turn_ids:
        scope += f" AND (turn_id IS NULL OR turn_id IN {_in(turn_ids)})"
    rows = con.execute(
        "SELECT chat_id, salience, importance, disputed, encoding_valence, "
        f"archived, kind, event_key FROM memories {scope}").fetchall()
    total = len(rows)
    out = [
        Row("memory bank", "importance revised",
            sum(1 for r in rows
                if r["importance"] is not None
                and r["salience"] is not None
                and abs(r["importance"] - r["salience"]) > 1e-9),
            total,
            "a consequence pointed back at this memory"),
        Row("memory bank", "disputed",
            sum(1 for r in rows if (r["disputed"] or "")), total,
            "this mind re-read what the memory meant"),
        Row("memory bank", "archived",
            sum(1 for r in rows if r["archived"]), total, ""),
        Row("memory bank", "has a stable event_key",
            sum(1 for r in rows if (r["event_key"] or "")), total,
            "without one it cannot be cited, disputed or effected"),
    ]
    # `encoding_valence` is `NOT NULL DEFAULT 0.0`, so a null test reports
    # 100% and means nothing: a row that never recorded one is indistinguishable
    # from a row that recorded neutral. Non-zero is the only honest proxy, and
    # it under-counts genuinely-neutral encodings by exactly the amount nobody
    # can measure. A NOT NULL DEFAULT is a fire rate you have given up.
    banks = {r["chat_id"] for r in rows}
    live_banks = {r["chat_id"] for r in rows
                  if (r["encoding_valence"] or 0.0) != 0.0}
    in_live = [r for r in rows if r["chat_id"] in live_banks]
    out.append(Row(
        "memory bank", "encoding_valence non-neutral",
        sum(1 for r in in_live if (r["encoding_valence"] or 0.0) != 0.0),
        len(in_live),
        f"{len(live_banks)} of {len(banks)} banks ever record one; "
        "NOT NULL DEFAULT 0.0 hides the rest"))
    return out


def salience_shape(con, chat_ids):
    """Not a fire rate -- a distribution. A term that always fires but always
    fires at the same value is doing nothing, and only the histogram shows it.
    """
    if not chat_ids:
        return {}
    rows = con.execute(
        "SELECT salience, importance FROM memories "
        f"WHERE chat_id IN {_in(chat_ids)}").fetchall()
    hist = Counter()
    values = []
    for r in rows:
        v = r["importance"] if r["importance"] is not None else r["salience"]
        if v is None:
            continue
        values.append(v)
        hist[min(9, max(0, int(v * 10)))] += 1
    if not values:
        return {}
    values.sort()
    n = len(values)
    return {
        "n": n,
        "mean": sum(values) / n,
        "median": values[n // 2],
        "p10": values[int(n * 0.10)],
        "p90": values[int(n * 0.90)],
        "spread_p10_p90": values[int(n * 0.90)] - values[int(n * 0.10)],
        "histogram": {f"{d/10:.1f}-{(d+1)/10:.1f}": hist[d] for d in range(10)},
        "modal_band_share": max(hist.values()) / n,
    }


# ----------------------------------------------------------- character output

def character_results(con, turn_ids):
    """Every per-mind result in scope, flattened."""
    if not turn_ids:
        return []
    keys = ",".join(f"'{k}'" for k in CHARACTER_STEPS)
    sql = ("SELECT v.content FROM variants v JOIN steps s ON s.id=v.step_id "
           f"WHERE v.active=1 AND s.turn_id IN {_in(turn_ids)} "
           f"AND (s.key IN ({keys}) OR s.key LIKE 'character:%')")
    out = []
    for row in con.execute(sql):
        try:
            blob = json.loads(row["content"])
        except (TypeError, ValueError):
            continue
        if not isinstance(blob, dict):
            continue
        results = blob.get("character_results")
        if isinstance(results, dict):
            results = list(results.values())
        elif not isinstance(results, list):
            # A `character:<id>` step stores the single result directly.
            results = [blob] if "appraisal" in blob else []
        out.extend(r for r in results if isinstance(r, dict))
    return out


def output_rows(results):
    rows = []
    for field, note in RESULT_FIELDS:
        chances = sum(1 for r in results if field in r)
        fired = sum(1 for r in results if field in r and not _empty(r[field]))
        rows.append(Row("character output", field, fired, chances, note))
    return rows


# ------------------------------------------------------------------ pipeline

def pipeline_rows(con, turn_ids):
    """Stages are a plan built per turn, so a stage that never appears is a
    branch the Director never took -- indistinguishable from a broken gate
    without this number."""
    if not turn_ids:
        return []
    counts = Counter()
    for r in con.execute(
            f"SELECT key FROM steps WHERE turn_id IN {_in(turn_ids)}"):
        counts[r["key"]] += 1
    turns = len(turn_ids)
    named = [("reaction_loop", "contested physical reactions"),
             ("interaction_loop", "sequenced conversation"),
             ("background_react", "an unregistered presence reacted"),
             ("mapping_stage", "full spatial mapping"),
             ("mapping_quick", "cheap spatial refresh"),
             ("narrator_extra", "a second narration pass")]
    rows = [Row("pipeline", key, counts[key], turns, note)
            for key, note in named]
    parallel = sum(v for k, v in counts.items() if k.startswith("character:"))
    rows.append(Row("pipeline", "character:<id> (parallel, no loop)",
                    parallel, turns, "uncontested independent reactions"))
    return rows


def offscreen_rows(con, turn_ids):
    """World-epoch opportunities and the work selected from them.

    Commit results are the denominator record: old turns that predate the
    `offscreen_epoch` domain are not chances, while a present false/empty field
    is an observed decline. This keeps a new mechanism from reading as dead
    merely because the corpus is mostly older than it.
    """
    if not turn_ids:
        return []
    sql = (
        "SELECT v.content FROM variants v JOIN steps s ON s.id=v.step_id "
        f"WHERE v.active=1 AND s.turn_id IN {_in(turn_ids)} "
        "AND s.key='commit'"
    )
    epochs = []
    plan_commits = []
    carrier_commits = []
    crowd_commits = []
    residue_commits = []
    for row in con.execute(sql):
        try:
            blob = json.loads(row["content"])
        except (TypeError, ValueError):
            continue
        result = ((blob.get("results") or {}).get("offscreen_epoch")
                  if isinstance(blob, dict) else None)
        if isinstance(result, dict) and "opportunity" in result:
            epochs.append(result)
        plans = ((blob.get("results") or {}).get("offscreen_plans")
                 if isinstance(blob, dict) else None)
        if isinstance(plans, dict) and "offered" in plans:
            plan_commits.append(plans)
        carriers = ((blob.get("results") or {}).get("information_carriers")
                    if isinstance(blob, dict) else None)
        if isinstance(carriers, dict) and "events_offered" in carriers:
            carrier_commits.append(carriers)
        crowd = ((blob.get("results") or {}).get("crowds")
                 if isinstance(blob, dict) else None)
        if isinstance(crowd, dict) and "offered" in crowd:
            crowd_commits.append(crowd)
        residue = ((blob.get("results") or {}).get("routine_residue")
                   if isinstance(blob, dict) else None)
        if isinstance(residue, dict) and "delivered" in residue:
            residue_commits.append(residue)

    opportunities = [e for e in epochs if e.get("opportunity")]
    actor_chances = [
        e for e in opportunities
        if e.get("eligible") and int(e.get("actors_considered") or 0) > 0
    ]
    profile_chances = [
        e for e in opportunities if e.get("profile_opportunity") is True
    ]
    agent_chances = [
        e for e in opportunities if e.get("agent_opportunity") is True
    ]
    return [
        Row("off-screen life", "world epoch opportunity",
            len(opportunities), len(epochs),
            "canonical location/time/due-event edge; older commits excluded"),
        Row("off-screen life", "seeded tick batch wrote events",
            sum(int(e.get("stochastic_fired") or 0) > 0 for e in actor_chances),
            len(actor_chances),
            "eligible epochs that had at least one dormant actor"),
        Row("off-screen life", "profile candidate selected",
            sum(int(e.get("profile_candidates") or 0) > 0
                for e in profile_chances),
            len(profile_chances),
            "model spend considered only on a world epoch"),
        Row("off-screen life", "profile job scheduled",
            sum(bool(e.get("profile_scheduled")) for e in profile_chances),
            len(profile_chances),
            "bounded, out of band; candidate selection is the preceding row"),
        Row("off-screen life", "full-agent candidate selected",
            sum(int(e.get("agent_candidates") or 0) > 0
                for e in agent_chances),
            len(agent_chances),
            "opted-in dormant mind with a private reason, on a world epoch"),
        Row("off-screen life", "full-agent job scheduled",
            sum(bool(e.get("agent_scheduled")) for e in agent_chances),
            len(agent_chances),
            "one reduced turn per candidate; landing is epoch-guarded"),
        Row("off-screen life", "reactive plan op accepted",
            sum(int(p.get("applied") or 0) for p in plan_commits),
            sum(int(p.get("offered") or 0) for p in plan_commits),
            "Director encoding grounded in that actor's declaration"),
        Row("off-screen life", "reactive stage fired",
            sum(int(e.get("reactive_fired") or 0) for e in opportunities),
            sum(int(e.get("reactive_considered") or 0) for e in opportunities),
            "one typed active stage considered per plan per world epoch"),
        Row("off-screen life", "reactive effect minted",
            sum(int(e.get("reactive_effects_minted") or 0)
                for e in opportunities),
            sum(int(e.get("reactive_effect_opportunities") or 0)
                for e in opportunities),
            "pre-adjudicated effect; no model call at firing"),
        Row("off-screen life", "public event surface emitted",
            sum(int(c.get("public_surfaces") or 0) for c in carrier_commits),
            sum(int(c.get("events_offered") or 0) for c in carrier_commits),
            "fired objective events; empty witnessed surfaces are real declines"),
        Row("off-screen life", "character acquired carried report",
            sum(int(c.get("acquired") or 0) for c in carrier_commits),
            sum(int(c.get("carrier_opportunities") or 0)
                for c in carrier_commits),
            "registered holder physically co-located with a public surface"),
        # Telling is the layer that makes the ledger epistemics rather than
        # bookkeeping. The denominator is ops the Director actually wrote, so
        # a refusal reads as a refusal and silence reads as `no chances` --
        # the distinction that cost four separate diagnoses to establish.
        Row("off-screen life", "a report was passed on",
            sum(int(c.get("told") or 0) for c in carrier_commits),
            sum(int(c.get("tellings_offered") or 0) for c in carrier_commits),
            "declared on-page; holding, speaking and co-location all checked"),
        # The road: bodies with positions. The denominator is ops the
        # Director wrote, so a refused dispatch reads as a refusal and a
        # story with no riders reads as `no chances`.
        Row("off-screen life", "a courier or caravan op was accepted",
            sum(int(c.get("couriers_offered") or 0)
                - int(c.get("courier_rejected") or 0)
                for c in carrier_commits),
            sum(int(c.get("couriers_offered") or 0)
                for c in carrier_commits),
            "declared on-page; holding, routes and co-location all checked"),
        # A caravan that dwells and trades nothing is a courier with extra
        # hops -- the exact cheap version the design deferred. Denominator
        # is stops actually reached, so an empty market reads honestly.
        Row("off-screen life", "a caravan traded news at a stop",
            sum(int(c.get("caravan_picked_up") or 0)
                + int(c.get("caravan_put_down") or 0)
                for c in carrier_commits),
            sum(int(c.get("caravan_stops") or 0) for c in carrier_commits),
            "a caravan dwelt at a stop; something legible or a crowd stood "
            "there"),
        Row("off-screen life", "an artifact op was accepted",
            sum(int(c.get("artifacts_posted") or 0)
                + int(c.get("artifacts_read") or 0)
                + int(c.get("artifacts_removed") or 0)
                for c in carrier_commits),
            sum(int(c.get("artifact_ops_offered") or 0)
                for c in carrier_commits),
            "declared on-page; holding and standing-at-the-wall checked"),
        Row("off-screen life", "a crowd op was accepted",
            sum(max(0, int(c.get("offered") or 0) - int(c.get("rejected") or 0))
                for c in crowd_commits),
            sum(int(c.get("offered") or 0) for c in crowd_commits),
            "a populous place declared as one object rather than as extras"),
        Row("off-screen life", "a crowd moved on the graph",
            sum(int(c.get("moved") or 0) for c in crowd_commits),
            sum(int(c.get("standing") or 0) for c in crowd_commits),
            "crowds standing anywhere; a heading is spent one beat after it "
            "is declared"),
        # A crowd is many witnesses; standing where a public surface lands is
        # its acquisition channel, exactly as a walking body's.
        Row("off-screen life", "a crowd took up public talk",
            sum(int(c.get("crowd_acquired") or 0) for c in carrier_commits),
            sum(int(c.get("crowd_opportunities") or 0)
                for c in carrier_commits),
            "crowd co-located with a public witnessed surface"),
        # Residue is computed on the Director payload path; the commit blob
        # echoes it (results.routine_residue) precisely so this table can see
        # it. The denominator is movement-declaring beats with the floor on --
        # a quiet beat gets no residue to deliver and is not a chance.
        Row("off-screen life", "destination residue delivered",
            sum(int(r.get("delivered") or 0) > 0 for r in residue_commits),
            len(residue_commits),
            "party moved somewhere; facts only where a ledger held any"),
    ]


# ------------------------------------------------------------------ capacity

def capacity_rows(con, chat_ids):
    """Whether the global caps are a safety valve or the actual shape of every
    character's attention. A cap that binds most minds most of the time is not
    limiting an outlier, it is the design.
    """
    if not chat_ids:
        return []
    want_cap, intent_cap, project_cap = 3, 4, 2
    wants = intents = projects = 0
    at_want = at_intent = at_project = 0
    want_total = intent_total = project_total = 0
    ever_project = 0
    for r in con.execute("SELECT state FROM chat_chars "
                         f"WHERE chat_id IN {_in(chat_ids)} "
                         "AND state IS NOT NULL AND state != ''"):
        try:
            state = json.loads(r["state"])
        except (TypeError, ValueError):
            continue
        if not isinstance(state, dict):
            continue
        active = state.get("active_state") or {}
        if isinstance(active, dict) and "wants" in active:
            n = len(active.get("wants") or [])
            wants += 1
            want_total += n
            at_want += (n >= want_cap)
        interior = state.get("interior") or {}
        if isinstance(interior, dict):
            if "intentions" in interior:
                n = sum(1 for i in (interior.get("intentions") or [])
                        if isinstance(i, dict) and i.get("status") == "active")
                intents += 1
                intent_total += n
                at_intent += (n >= intent_cap)
            if "projects" in interior:
                n = sum(1 for p in (interior.get("projects") or [])
                        if isinstance(p, dict) and p.get("status") != "ended")
                projects += 1
                project_total += n
                at_project += (n >= project_cap)
                # A cap only means something once the tier is reachable, so
                # measure the floor as well as the ceiling. Both ledgers: a
                # project adopted and since ended still proves the path ran.
                ever_project += bool(n or (interior.get("former_projects") or []))
    return [
        Row("capacity", f"wants at cap ({want_cap})", at_want, wants,
            f"mean {want_total/wants:.2f}" if wants else ""),
        Row("capacity", f"intentions at cap ({intent_cap})", at_intent, intents,
            f"mean {intent_total/intents:.2f}" if intents else ""),
        Row("capacity", "has ever held a project", ever_project, projects,
            "the tier is unreachable if this is zero"),
        Row("capacity", f"projects at cap ({project_cap})", at_project, projects,
            f"mean {project_total/projects:.2f}" if projects else ""),
    ]


# ------------------------------------------------------------------- report

def collect(con, chat=None, last=None):
    turn_ids, chat_ids = turn_scope(con, chat=chat, last=last)
    results = character_results(con, turn_ids)
    rows = (memory_rows(con, turn_ids, chat_ids)
            + output_rows(results)
            + pipeline_rows(con, turn_ids)
            + offscreen_rows(con, turn_ids)
            + capacity_rows(con, chat_ids))
    return {
        "scope": {"chats": len(chat_ids), "turns": len(turn_ids),
                  "character_results": len(results),
                  "last": last, "chat": chat},
        "mechanisms": [r.as_dict() for r in rows],
        "salience": salience_shape(con, chat_ids),
    }


def render(report) -> str:
    scope = report["scope"]
    lines = [
        f"scope: {scope['chats']} chats, {scope['turns']} turns, "
        f"{scope['character_results']} character results"
        + (f" (last {scope['last']} turns per chat)" if scope["last"] else ""),
        "",
    ]
    width = max((len(m["name"]) for m in report["mechanisms"]), default=20)
    layer = None
    for m in report["mechanisms"]:
        if m["layer"] != layer:
            layer = m["layer"]
            lines.append(f"  {layer.upper()}")
        if not m["chances"]:
            cell = "     no chances"
        else:
            cell = f"{m['rate']*100:7.2f}%  {m['fired']:>5}/{m['chances']:<5}"
        note = f"   {m['note']}" if m["note"] else ""
        lines.append(f"    {m['name']:<{width}}  {cell}{note}")
    sal = report.get("salience") or {}
    if sal:
        lines += ["", "  EFFECTIVE IMPORTANCE (the ranking term, not a rate)",
                  f"    n={sal['n']}  mean {sal['mean']:.3f}  "
                  f"median {sal['median']:.2f}  "
                  f"p10-p90 {sal['p10']:.2f}-{sal['p90']:.2f} "
                  f"(spread {sal['spread_p10_p90']:.2f})",
                  f"    modal band holds {sal['modal_band_share']*100:.1f}% "
                  f"of the corpus"]
        for band, count in sal["histogram"].items():
            bar = "#" * int(round(count / max(sal["histogram"].values()) * 40))
            lines.append(f"    {band}  {count:>5}  {bar}")
    return "\n".join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--db", default=os.environ.get("ENGINE_DB", "engine.db"))
    ap.add_argument("--last", type=int, default=None,
                    help="only the last N turns of each chat")
    ap.add_argument("--chat", type=int, default=None)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    con = connect(args.db)
    try:
        report = collect(con, chat=args.chat, last=args.last)
    finally:
        con.close()
    print(json.dumps(report, indent=2) if args.json else render(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
