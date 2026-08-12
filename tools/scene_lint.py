#!/usr/bin/env python3
"""Assert invariants over committed scenes, across every story at once.

NOT a search for known bugs. Every check here names one fact that TWO
representations both claim, and asks whether they answer it the same way --
wardrobe against entity, `wearing` against `regions`, `contained` against
`positions`, a derived note against the note that replaced it. A
contradiction is detectable whatever produced it, so this finds defect
classes nobody predicted, which is the whole reason it exists: the shed-
garment duplication was found by hand, one beat at a time, and the same
shape had been standing in other stories for weeks.

Two kinds of output, deliberately separate:

  INVARIANTS -- two ledgers disagreeing. A real defect in every case.
  STRUCTURE  -- a scene written by an older engine that current code has to
                cope with. Not a defect; an answer to "will old stories
                still work", which is a different question and must not be
                mixed into the first one.

Usage:
    python tools/scene_lint.py                 # report every chat
    python tools/scene_lint.py --chat 71       # one story
    python tools/scene_lint.py --heal          # repair what is safely
                                               # healable, via the engine's
                                               # own canonical helpers
    python tools/scene_lint.py --heal --dry-run

Healing uses `attire.release_removed_garments` (which reder1ves the entry,
dropping stale derived notes) and `commit._fold_duplicate_shed_garments`.
Both are the code the live path already runs; this only reaches scenes that
stopped being written to before those existed. Checkpoints are healed
alongside the live scene, because a reroll restores from them.
"""
from __future__ import annotations

import argparse
import collections
import json
import os
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import attire  # noqa: E402
import commit  # noqa: E402


# --- invariants -------------------------------------------------------------

def _worn_names(attire_map, owner):
    entry = attire_map.get(owner) or {}
    return [str(x) for x in (entry.get("wearing") or []) if str(x).strip()]


def check_scene(sc):
    """Every disagreement in one scene, as (kind, detail) pairs."""
    out = []
    if not isinstance(sc, dict):
        return out
    ents = sc.get("entities") or {}
    attire_map = sc.get("attire") or {}
    rooms = sc.get("rooms") or {}
    positions = sc.get("positions") or {}
    contained = sc.get("contained") or {}

    # An entity claiming to be worn that the wardrobe does not carry. While
    # a garment is worn the attire ledger owns it; a second record saying
    # otherwise is the one that is wrong.
    for eid, e in ents.items():
        st = (e or {}).get("state") or {}
        if not st.get("clothing") or st.get("shed"):
            continue
        owner = str(st.get("worn_by") or "").strip()
        name = str((e or {}).get("name") or "")
        if not owner or not name:
            continue
        if not attire.resolve_garment(name, _worn_names(attire_map, owner)):
            out.append(("entity says worn, wardrobe disagrees",
                        f"{eid}={name!r} worn_by={owner}"))

    # Several records for one shed garment. An unowned record and an owned
    # one are the live shape (the model's, and the commit seam's mint).
    groups = []
    for eid, e in ents.items():
        st = (e or {}).get("state") or {}
        if not (st.get("clothing") and st.get("shed")):
            continue
        name = str((e or {}).get("name") or "").strip()
        owner = str(st.get("worn_by") or "").strip().casefold()
        if not name:
            continue
        for g in groups:
            if g["owner"] and owner and g["owner"] != owner:
                continue
            if attire.resolve_garment(name, [g["name"]]) or \
                    attire.resolve_garment(g["name"], [name]):
                g["ids"].append(eid)
                g["owner"] = g["owner"] or owner
                break
        else:
            groups.append({"owner": owner, "name": name, "ids": [eid]})
    for g in groups:
        if len(g["ids"]) > 1:
            out.append(("duplicate shed-garment records",
                        f"{g['name']!r} -> {g['ids']}"))

    for who, entry in attire_map.items():
        regions = (entry or {}).get("regions") or {}
        # A garment that came off, still seated on the body it left.
        for reg, body in regions.items():
            for garment in (body or {}).get("garments") or []:
                if isinstance(garment, dict) and garment.get("state") == "removed":
                    out.append(("removed garment still in a region",
                                f"{who}/{reg}: {garment.get('name')!r}"))
        # `wearing` and `regions` are the same wardrobe said twice.
        resident = {str(g.get("name")) for body in regions.values()
                    for g in (body or {}).get("garments") or []
                    if isinstance(g, dict) and g.get("state") != "removed"}
        if resident:
            for name in _worn_names(attire_map, who):
                if not attire.resolve_garment(name, sorted(resident)):
                    out.append(("wearing names a garment no region holds",
                                f"{who}: {name!r}"))
        # A derived note this engine emitted on an earlier beat, preserved
        # as though authored. They are each true of a different moment and
        # contradictory as a set, which is what a mind reading `state` gets.
        bare = [n for n in ((entry or {}).get("state") or [])
                if isinstance(n, str) and n.casefold().startswith("bare at the ")]
        if len(bare) > 1:
            out.append(("several contradictory derived state notes",
                        f"{who}: {bare}"))

    # A body inside something, and a room position claiming otherwise.
    for subject in contained:
        if subject in positions:
            out.append(("contained body also has its own position",
                        str(subject)))

    # A position naming something that is not a room. Split deliberately:
    # a carried object positioned ON ITS CARRIER is existing law, not a
    # defect, and lumping the two together would report a working feature.
    nameable = set(rooms) | set(ents) | set(attire_map)
    named = {str((e or {}).get("name") or "") for e in ents.values()}
    named |= set(attire_map)
    for subject, where in positions.items():
        if not where or where in rooms:
            continue
        if where in nameable or where in named:
            out.append(("position names a carrier rather than a room",
                        f"{subject} -> {where!r}"))
        else:
            out.append(("position names nothing that exists",
                        f"{subject} -> {where!r}"))
    return out


# --- structure age ----------------------------------------------------------

def check_structure(sc):
    """How OLD this scene's shape is. Not defects -- compatibility facts."""
    out = []
    if not isinstance(sc, dict):
        return ["scene is not an object"]
    for key in ("rooms", "positions", "entities", "attire"):
        if key not in sc:
            out.append(f"no {key!r} key")
    for who, entry in (sc.get("attire") or {}).items():
        if not isinstance(entry, dict):
            out.append(f"attire[{who}] is {type(entry).__name__}, not an object")
            continue
        if "regions" not in entry:
            out.append("attire entry with no 'regions' (pre-region wardrobe)")
        if "wearing" not in entry:
            out.append("attire entry with no 'wearing'")
    for eid, e in (sc.get("entities") or {}).items():
        if not isinstance(e, dict):
            out.append(f"entity {eid} is not an object")
        elif "kind" not in e:
            out.append("entity with no 'kind'")
    return out


# --- healing ----------------------------------------------------------------

def heal_scene(sc):
    """Repair the invariant violations, and NOTHING else.

    Deliberately NOT `attire.release_removed_garments`, though that is the
    canonical live-path repair. It calls `rederive_entry`, which rebuilds
    `wearing` from `regions` -- correct on a scene the current engine
    wrote, destructive on an old one. Measured across this corpus before
    running anything: it would have rewritten 127 pre-region wardrobes into
    the region model, and in ten places changed a garment's NAME --
    'rank pips: four' to 'rank pips', 'sheer obsidian silk robe that parts
    with every movement' to 'sheer obsidian silk robe'. A repair tool that
    quietly renames a character's clothes across fifty stories is worse
    than the contradiction it fixes.

    So: only entries the current engine already owns (a real `regions`
    map), only the garments that provably left the body, only stale notes
    this engine itself emitted, and `wearing` edited by REMOVAL rather than
    recomputed. A pre-region wardrobe is left exactly as it is -- current
    code copes with it, and migrating it is a separate decision.
    """
    changed = False
    for entry in (sc.get("attire") or {}).values():
        if not isinstance(entry, dict):
            continue
        regions = entry.get("regions")
        if not isinstance(regions, dict) or not regions:
            continue          # pre-region wardrobe: not ours to rewrite
        gone = []
        for region in regions.values():
            if not isinstance(region, dict):
                continue
            garments = region.get("garments")
            if not isinstance(garments, list):
                continue
            kept = [g for g in garments
                    if not (isinstance(g, dict) and g.get("state") == "removed")]
            if len(kept) != len(garments):
                gone += [str(g.get("name")) for g in garments
                         if isinstance(g, dict) and g.get("state") == "removed"]
                region["uncovered"] = True
                region["garments"] = kept
                changed = True
        if gone:
            # By removal, never by recompute: an exact name that is no
            # longer worn goes, and every other spelling stays untouched.
            wearing = [w for w in (entry.get("wearing") or [])
                       if str(w) not in gone]
            if wearing != entry.get("wearing"):
                entry["wearing"] = wearing
        # Stale derived notes: keep the one that matches the wardrobe as it
        # now stands, drop the ones this engine emitted on earlier beats.
        notes = [n for n in (entry.get("state") or []) if isinstance(n, str)]
        bare = [n for n in notes if n.casefold().startswith("bare at the ")]
        if len(bare) > 1:
            current = attire.flat_state(regions)
            keep = [n for n in bare if n in current] or bare[:1]
            entry["state"] = [n for n in notes
                              if n not in bare or n in keep[:1]]
            changed = True
    before = json.dumps(sc.get("entities") or {}, sort_keys=True)
    commit._fold_duplicate_shed_garments(sc)
    if json.dumps(sc.get("entities") or {}, sort_keys=True) != before:
        changed = True
    return changed


# --- driver -----------------------------------------------------------------

def _scene_of(blob):
    sc = blob.get("world", {}).get("scene") if isinstance(blob, dict) else None
    return json.loads(sc) if isinstance(sc, str) else sc


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="engine.db")
    ap.add_argument("--chat", type=int, default=None)
    ap.add_argument("--heal", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--quiet-structure", action="store_true")
    args = ap.parse_args()

    read_only = f"file:{args.db}?mode=ro"
    src = sqlite3.connect(read_only, uri=True)
    work = sqlite3.connect(":memory:")
    src.backup(work)
    work.row_factory = sqlite3.Row

    rows = work.execute(
        "SELECT chat_id, value FROM world WHERE key='scene'"
        + (" AND chat_id=?" if args.chat else ""),
        (args.chat,) if args.chat else ()).fetchall()

    findings = collections.Counter()
    structure = collections.Counter()
    examples, struct_examples = {}, {}
    healable = []

    for row in rows:
        try:
            sc = json.loads(row["value"])
        except Exception:
            findings["scene will not parse"] += 1
            continue
        for kind, detail in check_scene(sc):
            findings[kind] += 1
            examples.setdefault(kind, (row["chat_id"], detail))
        for note in check_structure(sc):
            structure[note] += 1
            struct_examples.setdefault(note, row["chat_id"])
        probe = json.loads(json.dumps(sc))
        if heal_scene(probe):
            healable.append(row["chat_id"])

    print("=" * 70)
    print(f"INVARIANTS — ledgers that disagree ({len(rows)} scenes)")
    print("=" * 70)
    if not findings:
        print("  none")
    for kind, n in findings.most_common():
        cid, detail = examples[kind]
        print(f"  {n:>5}  {kind}")
        print(f"         e.g. chat {cid}: {detail}")

    if not args.quiet_structure:
        print()
        print("=" * 70)
        print("STRUCTURE — older shapes current code must cope with")
        print("=" * 70)
        if not structure:
            print("  every scene carries the current shape")
        for note, n in structure.most_common():
            print(f"  {n:>5}  {note}   (e.g. chat {struct_examples[note]})")

    print()
    print(f"scenes with something healable: {sorted(set(healable))}")

    if args.heal:
        target = sqlite3.connect(args.db, timeout=30)
        target.execute("PRAGMA busy_timeout=30000")
        target.row_factory = sqlite3.Row
        healed_scenes = healed_ckpts = 0
        for row in target.execute(
                "SELECT chat_id, value FROM world WHERE key='scene'"
                + (" AND chat_id=?" if args.chat else ""),
                (args.chat,) if args.chat else ()).fetchall():
            sc = json.loads(row["value"])
            if heal_scene(sc):
                healed_scenes += 1
                if not args.dry_run:
                    target.execute(
                        "UPDATE world SET value=? WHERE chat_id=? AND key='scene'",
                        (json.dumps(sc), row["chat_id"]))
        # A reroll restores from a checkpoint, so a scene healed only in
        # `world` would be un-healed the moment the story is rerolled.
        for row in target.execute(
                "SELECT id, chat_id, blob FROM checkpoints"
                + (" WHERE chat_id=?" if args.chat else ""),
                (args.chat,) if args.chat else ()).fetchall():
            try:
                blob = json.loads(row["blob"])
                sc = _scene_of(blob)
            except Exception:
                continue
            if not isinstance(sc, dict):
                continue
            as_str = isinstance(blob.get("world", {}).get("scene"), str)
            if heal_scene(sc):
                healed_ckpts += 1
                blob["world"]["scene"] = json.dumps(sc) if as_str else sc
                if not args.dry_run:
                    target.execute("UPDATE checkpoints SET blob=? WHERE id=?",
                                   (json.dumps(blob), row["id"]))
        if not args.dry_run:
            target.commit()
        target.close()
        print(f"{'would heal' if args.dry_run else 'healed'}: "
              f"{healed_scenes} scenes, {healed_ckpts} checkpoints")


if __name__ == "__main__":
    main()
