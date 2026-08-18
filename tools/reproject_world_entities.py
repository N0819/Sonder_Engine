#!/usr/bin/env python3
"""Re-derive world_entities from the scene blob it is a projection of.

`commit_world_entities` used to write the RAW validated diff into
world_entities while `merge_scene_with_diff` merged the same diff into the
scene blob -- and the merge reads a schema default as silence and refuses a
name the validator derived from the dict key. So a pose-only beat left the
blob saying "Blue Police Box"/vehicle and the durable row saying "Tardis
001"/object. Measured on the author's engine.db before the fix:

    480 rows, 471 still present in their chat's scene blob
     15 named literally 'Object' (3.1%) -- 12 with a real name in the blob
     19 disagreeing with the blob about `name`
     24 disagreeing with the blob about `kind`

The fix projects the merged entity, so any entity a later beat touches heals
itself. This tool is for the ones nothing will touch again: an object in a
story that has stopped. It re-runs the projection -- it does not guess, it
copies from the source the table is derived from.

    python3 tools/reproject_world_entities.py            # report, write nothing
    python3 tools/reproject_world_entities.py --chat 59
    python3 tools/reproject_world_entities.py --apply    # repair

Read-only unless --apply is passed, so it is safe to run against a live
engine.db while the server is up. --apply takes the write lock; stop the
server first. A row absent from the blob is left exactly alone: the blob is
the authority only about entities it still holds, and silence there is not a
statement about the row.

Checkpoints and chat archives carry their OWN world_entities snapshots, taken
before this ran, so restoring an old one reintroduces the old rows. That is
not a gap this tool can close -- it is why the fix in commit.py, which heals
on next touch, is the load-bearing half and this is the sweep.
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# The same predicate the merge and the commit projection use. Imported rather
# than restated: a repair that disagreed with the rule it repairs toward would
# undo itself on the next beat. `schemas` is pure at import.
from llm.schemas import is_derived_entity_name  # noqa: E402

FIELDS = ("kind", "subtype", "name")


def connect(path, *, write=False):
    if write:
        return sqlite3.connect(path)
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    return con


def _scene_entities(con, chat_id):
    """Every scene blob this chat has, as a list of its `entities` maps.

    `world_entities` has no per-frame partitioning and `scene` does (db's
    `_scoped_world_key`), so a chat with frames has several blobs feeding one
    table -- three of them in the author's corpus. Which frame is live is a
    question the engine answers per run and this sweep has no business
    guessing, so it collects them all and only repairs where they agree.
    """
    out = []
    for (value,) in con.execute(
            "SELECT value FROM world WHERE chat_id=? AND "
            "(key='scene' OR key LIKE 'scene' || ? || '%')",
            (chat_id, "\x1efr")).fetchall():
        try:
            blob = json.loads(value or "null")
        except (TypeError, ValueError):
            continue
        entities = (blob or {}).get("entities")
        if isinstance(entities, dict):
            out.append(entities)
    return out


def reprojected(entity_id, row, blob_entity):
    """The row this entity should have, or None if it is already right.

    `row` and the return are {kind, subtype, name, payload}. The blob wins on
    every field EXCEPT a name it would only be handing back a placeholder for:
    a row that already carries a real name keeps it, because an id rekey can
    leave the durable row holding the better spelling and the repair must
    never be the thing that mints an 'Object'.
    """
    if not isinstance(blob_entity, dict):
        return None
    want = {
        "kind": str(blob_entity.get("kind") or "object"),
        "subtype": str(blob_entity.get("subtype") or ""),
        "name": str(blob_entity.get("name") or "").strip(),
        "payload": json.dumps(blob_entity, ensure_ascii=False),
    }
    row_name = str(row.get("name") or "").strip()
    if not want["name"] or (
        row_name
        and not is_derived_entity_name(entity_id, row_name, row.get("kind"))
        and is_derived_entity_name(entity_id, want["name"],
                                   want["kind"])
    ):
        want["name"] = row_name
    if all(str(row.get(f) or "") == want[f] for f in FIELDS) \
            and str(row.get("payload") or "") == want["payload"]:
        return None
    return want


def collect(con, chat=None):
    sql = ("SELECT entity_id, chat_id, kind, subtype, name, payload "
           "FROM world_entities")
    args = ()
    if chat is not None:
        sql += " WHERE chat_id=?"
        args = (chat,)
    scenes = {}
    findings = []
    ambiguous = []
    total = 0
    for entity_id, chat_id, kind, subtype, name, payload in \
            con.execute(sql, args).fetchall():
        total += 1
        if chat_id not in scenes:
            scenes[chat_id] = _scene_entities(con, chat_id)
        holders = [e[entity_id] for e in scenes[chat_id]
                   if isinstance(e.get(entity_id), dict)]
        if not holders:
            continue
        row = {"kind": kind, "subtype": subtype, "name": name,
               "payload": payload}
        wants = [reprojected(entity_id, row, h) for h in holders]
        if any(w != wants[0] for w in wants[1:]):
            # Two frames of one chat describe this entity differently. Both
            # are legitimate; the table can hold only one, and picking is a
            # decision about frames, not a repair.
            ambiguous.append({"entity_id": entity_id, "chat_id": chat_id})
            continue
        want = wants[0]
        if want:
            findings.append({"entity_id": entity_id, "chat_id": chat_id,
                             "was": {f: row[f] for f in FIELDS},
                             "now": {f: want[f] for f in FIELDS},
                             "payload": want["payload"]})
    return {"rows": total, "diverged": findings, "ambiguous": ambiguous}


def apply(con, findings):
    for f in findings:
        con.execute(
            "UPDATE world_entities SET kind=?,subtype=?,name=?,payload=? "
            "WHERE entity_id=? AND chat_id=?",
            (f["now"]["kind"], f["now"]["subtype"], f["now"]["name"],
             f["payload"], f["entity_id"], f["chat_id"]))
    con.commit()
    return len(findings)


def render(report):
    lines = [f"{report['rows']} rows, {len(report['diverged'])} disagreeing "
             f"with the scene blob"]
    for f in report["diverged"]:
        changed = [x for x in FIELDS if f["was"][x] != f["now"][x]]
        detail = ", ".join(f"{x}: {f['was'][x]!r} -> {f['now'][x]!r}"
                           for x in changed) or "payload only"
        lines.append(f"  chat {f['chat_id']:>4}  {f['entity_id']:<24} {detail}")
    for a in report.get("ambiguous") or []:
        lines.append(f"  chat {a['chat_id']:>4}  {a['entity_id']:<24} "
                     f"SKIPPED: this chat's frames disagree about it")
    return "\n".join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--db", default=os.environ.get("ENGINE_DB", "engine.db"))
    ap.add_argument("--chat", type=int, default=None)
    ap.add_argument("--apply", action="store_true",
                    help="write the repair (default: report only)")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    con = connect(args.db, write=args.apply)
    try:
        report = collect(con, chat=args.chat)
        if args.apply:
            report["applied"] = apply(con, report["diverged"])
    finally:
        con.close()
    print(json.dumps(report, indent=2) if args.json else render(report))
    if args.apply and not args.json:
        print(f"applied to {report['applied']} rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
