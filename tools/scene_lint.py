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

Healing uses `commit._fold_duplicate_shed_garments` (defined in
`persist/commit_attire.py`, re-exported by the facade), which is the code the
live path already runs; this only reaches scenes that stopped being written to
before it existed. `--heal` also restores `uncovered` where a chat's own
checkpoints prove a garment left a region -- see `observe_exposure`, and note
that this one reads a chat's history in turn order rather than one scene at a
time, because no single scene carries the difference between a region that was
stripped and one that was never dressed. It deliberately does NOT use
`attire.release_removed_garments`, the other canonical repair, because that
rederives the entry and would rewrite pre-region wardrobes -- the reason, and
what it was measured to do to this corpus, are in `heal_scene`'s own docstring.
Checkpoints are healed alongside the live scene, because a reroll restores from
them.
"""
from __future__ import annotations

import argparse
import collections
import json
import os
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from story import attire  # noqa: E402
from world.spatial import ROOM_SIZES  # noqa: E402
from persist import commit  # noqa: E402


# --- invariants -------------------------------------------------------------

def _worn_names(attire_map, owner):
    entry = attire_map.get(owner) or {}
    return [str(x) for x in (entry.get("wearing") or []) if str(x).strip()]


def scene_subjects(sc):
    """Every name this scene treats as a PRESENT SUBJECT, from the ledgers
    that only bodies appear in. Derived from the scene itself, so a check
    built on it needs no outside truth to call a reference dangling."""
    subjects = set()
    for key in ("attire", "poses", "stations", "overlays", "orientation"):
        value = sc.get(key)
        if isinstance(value, dict):
            subjects |= {str(k) for k in value}
    entities = set(sc.get("entities") or {})
    for subject in (sc.get("positions") or {}):
        if subject not in entities:
            subjects.add(str(subject))
    return subjects


def check_references(sc):
    """DANGLING REFERENCES, across every ledger in the fiction.

    The generalisation of the garment work: a ledger that names a subject,
    a room or an object which no other ledger carries is the same defect
    shape as two records of one garment -- one representation asserting
    something the rest of the world cannot answer for. It costs nothing to
    check for every ledger at once, and it is not about clothing.
    """
    out = []
    subjects = scene_subjects(sc)
    rooms = set(sc.get("rooms") or {})
    entities = set(sc.get("entities") or {})
    named_entities = {str((e or {}).get("name") or "")
                      for e in (sc.get("entities") or {}).values()}
    # Room ANCHORS are first-class places a body can be stationed at or
    # supported by -- `comfort.py` resolves station.at against them. Left
    # out of this set on the first pass, which reported 33 stations and 9
    # poses as dangling when every one of them was correct. An invariant
    # checked against the wrong idea of the world produces confident
    # nonsense, which is worse than no check.
    anchors = {str(a) for room in (sc.get("rooms") or {}).values()
               if isinstance(room, dict)
               for a in (room.get("anchors") or {})}
    # Generic ground a body can rest on without the world modelling it.
    surfaces = {"floor", "ground", "the floor", "the ground"}
    places = rooms | entities | named_entities | anchors | surfaces

    def known_subject(name):
        return not name or name in subjects

    # --- who is touching whom -------------------------------------------
    for op in (sc.get("contacts") or []):
        if not isinstance(op, dict):
            continue
        for role in ("a", "b", "actor", "target", "subject"):
            who = str(op.get(role) or "").strip()
            if who and not known_subject(who) and who not in places:
                out.append(("contact names a subject the scene does not carry",
                            f"{role}={who!r}"))

    # --- what is on or in what ------------------------------------------
    for subject, holder in (sc.get("contained") or {}).items():
        ref = holder.get("in") if isinstance(holder, dict) else holder
        ref = str(ref or "").strip()
        if ref and ref not in places:
            out.append(("contained in something that does not exist",
                        f"{subject} in {ref!r}"))
    # A containment cycle is a world that cannot be rendered at all.
    contained = {k: (v.get("in") if isinstance(v, dict) else v)
                 for k, v in (sc.get("contained") or {}).items()}
    for start in contained:
        seen, node = set(), start
        while node in contained and node not in seen:
            seen.add(node)
            node = contained[node]
        if node in seen:
            out.append(("containment cycle", f"{start} -> ... -> {node}"))

    # --- substances, scales, overlays -----------------------------------
    for op in (sc.get("substances") or []):
        if not isinstance(op, dict):
            continue
        for role in ("source", "target"):
            who = str(op.get(role) or "").strip()
            if who and not known_subject(who) and who not in places:
                out.append(("substance names a subject the scene does not carry",
                            f"{role}={who!r} ({op.get('substance')!r})"))
    for who in (sc.get("scales") or {}):
        if not known_subject(str(who)):
            out.append(("scale for a subject the scene does not carry", str(who)))

    # --- posture and bearing --------------------------------------------
    for who, pose in (sc.get("poses") or {}).items():
        if not isinstance(pose, dict):
            continue
        rel = str(pose.get("relative_to") or "").strip()
        if rel and not known_subject(rel):
            out.append(("pose relative to a subject the scene does not carry",
                        f"{who} -> {rel!r}"))
        support = str(pose.get("support") or "").strip()
        if support and support not in places:
            out.append(("pose supported by something that does not exist",
                        f"{who} on {support!r}"))
    for who, facing in (sc.get("orientation") or {}).items():
        focus = (facing or {}).get("focus") if isinstance(facing, dict) else None
        ref = str((focus or {}).get("ref") or "").strip()
        if ref and not known_subject(ref) and ref not in places:
            out.append(("orientation focused on something that does not exist",
                        f"{who} -> {ref!r}"))
        came = str((facing or {}).get("came_from") or "").strip()
        if came and came not in rooms:
            out.append(("came_from names a room that does not exist",
                        f"{who} <- {came!r}"))

    # --- stations and company -------------------------------------------
    for who, station in (sc.get("stations") or {}).items():
        if not isinstance(station, dict):
            continue
        at = str(station.get("at") or "").strip()
        if at and at not in places:
            out.append(("station at something that does not exist",
                        f"{who} at {at!r}"))
        for near in (station.get("near") or []):
            if not known_subject(str(near)):
                out.append(("station near a subject the scene does not carry",
                            f"{who} near {near!r}"))

    # --- who follows whom ------------------------------------------------
    following = {k: (v.get("target") if isinstance(v, dict) else v)
                 for k, v in (sc.get("following") or {}).items()}
    for who, target in following.items():
        if not known_subject(str(who)):
            out.append(("follower the scene does not carry", str(who)))
        if target and not known_subject(str(target)):
            out.append(("following a subject the scene does not carry",
                        f"{who} -> {target!r}"))
    for start in following:
        seen, node = set(), start
        while node in following and node not in seen:
            seen.add(node)
            node = following[node]
        if node in seen:
            out.append(("following cycle", f"{start} -> ... -> {node}"))

    # --- the geography itself --------------------------------------------
    for rid, room in (sc.get("rooms") or {}).items():
        if not isinstance(room, dict):
            continue
        for edge in (room.get("adjacent") or []):
            ref = edge.get("to") if isinstance(edge, dict) else edge
            ref = str(ref or "").strip()
            if ref and ref not in rooms:
                out.append(("adjacency leads to a room that does not exist",
                            f"{rid} -> {ref!r}"))
    return out


def check_scene(sc):
    """Every disagreement in one scene, as (kind, detail) pairs."""
    out = []
    if not isinstance(sc, dict):
        return out
    out += check_references(sc)
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


# --- exposure history -------------------------------------------------------

# `uncovered` is the flag `perceptible_region_surfaces` reads before it will
# print a region's authored `beneath`: this region had something on it and no
# longer does. It is DURABLE history about the body -- a region stays
# uncovered until something covers it again -- and until `88aee71`
# `attire.advance` rebuilt each region without carrying it, so the flag lived
# exactly one beat and the next wardrobe change anywhere on that body wiped
# it. Measured in chat 86, one checkpoint per turn, garments coming off across
# t10-t15 (`(worn count, uncovered)` per region):
#
#     t10  arms  (0, True)   ->  t12  arms  (0, False)
#     t12  torso (0, True)   ->  t13  torso (0, False)
#     t13  waist (0, True)   ->  t14  waist (0, False)
#     t14  groin (0, True)   ->  t15  groin (0, False)
#     t14  legs  (0, True)   ->  t15  legs  (0, False)
#     t15  feet  (0, True)   ->  t45  feet  (0, True)
#
# Feet survived only because nothing proposed that region again. The result on
# the page: a body bare everywhere rendered its authored surface for ONE region
# and the bare word `bare` for the other five, and the five could never
# recover -- the licence is earned by a garment leaving, and they had no
# garment left to lose.
#
# THE REPAIR IS NOT INFERENCE. Nothing inside a ledger entry distinguishes
# "this was stripped in play" from "this was never clothed" -- Tamamo's head
# and hands and Mirelle's hands and feet are bare, carry authored `beneath`,
# and are correctly silent, because no garment ever left them. The chat's own
# checkpoints hold the difference: they recorded the flag on the beat it was
# set and the garment on the beats before that. This replays that history
# forward and restores what `advance` should have carried.


def _worn_garments(region):
    """Garments actually covering this region -- ornaments and departed
    garments are not coverings, which is the same test `attire` itself
    applies before deciding a region is bare."""
    return [g for g in (region.get("garments") or [])
            if isinstance(g, dict) and not g.get("attaches")
            and g.get("state") != "removed"]


def _already_licensed(region):
    """Whether this region can already print its `beneath`. EITHER signal,
    matching `attire.perceptible_region_surfaces`: the flag, or a garment
    still sitting here under `state: "removed"` (an older engine's spelling
    of the same fact)."""
    return bool(region.get("uncovered")) or any(
        isinstance(g, dict) and g.get("state") == "removed"
        for g in (region.get("garments") or []))


def strip_state_word_garments(sc):
    """Garments whose whole name is a body state, not a thing worn.

    `attire.is_bare_garment_state` is the live path's own test and now refuses
    these on the way in; what it cannot do is unwear the ones already stored.
    Measured across this corpus: seven bodies in four stories, every one of
    them on the TORSO, because a name no garment table recognises falls to the
    region fallback and lands there. So the fault is never cosmetic -- a body
    is reported clothed at the chest by the word `removed`, `worn`, or the
    surface it was meant to describe.

    Removed BEFORE the exposure pass reads a scene, for two reasons: a phantom
    covering hides the very transition that pass looks for, and a region the
    phantom is sitting on cannot be relicensed while something appears to
    cover it.

    Its departure is NOT evidence of a baring, and nothing here sets
    `uncovered`. It never covered anything, so it cannot have uncovered
    anything by leaving; only the real garments in a chat's history can earn
    that flag.
    """
    changed = False
    if not isinstance(sc, dict):
        return False
    for entry in (sc.get("attire") or {}).values():
        if not isinstance(entry, dict):
            continue
        gone = []
        regions = entry.get("regions")
        if isinstance(regions, dict):
            for region in regions.values():
                if not isinstance(region, dict):
                    continue
                garments = region.get("garments")
                if not isinstance(garments, list):
                    continue
                kept = [g for g in garments
                        if not (isinstance(g, dict)
                                and attire.is_bare_garment_state(g.get("name")))]
                if len(kept) != len(garments):
                    gone += [str(g.get("name")) for g in garments
                             if isinstance(g, dict)
                             and attire.is_bare_garment_state(g.get("name"))]
                    region["garments"] = kept
                    changed = True
        # By removal, never by recompute -- `heal_scene`'s rule, for its
        # reason: a pre-region wardrobe rebuilt from `regions` loses names.
        wearing = [w for w in (entry.get("wearing") or [])
                   if not attire.is_bare_garment_state(w)]
        if wearing != (entry.get("wearing") or []):
            entry["wearing"] = wearing
            changed = True
    return changed


def observe_exposure(sc, known, worn_before):
    """Fold one scene from a chat's history into what that history proves.

    `known` is {body: {regions known uncovered by now}} and `worn_before` is
    {(body, region): was covered at the previous observation}; both are
    mutated, so calling this over a chat's checkpoints in TURN ORDER leaves
    `known` holding exactly what was true by the last one. Order is the whole
    method: a flag restored onto an earlier checkpoint than the beat that
    earned it would assert a body was bared before it was.
    """
    if not isinstance(sc, dict):
        return
    for body, entry in (sc.get("attire") or {}).items():
        regions = (entry or {}).get("regions")
        if not isinstance(regions, dict):
            continue
        for region_name, region in regions.items():
            if not isinstance(region, dict):
                continue
            key = (body, region_name)
            covered_now = bool(_worn_garments(region))
            if _already_licensed(region):
                known.setdefault(body, set()).add(region_name)
            elif worn_before.get(key) and not covered_now:
                # A garment was here and is gone. The beat that set the flag
                # may itself have been overwritten before this checkpoint was
                # taken, so the transition is evidence in its own right.
                known.setdefault(body, set()).add(region_name)
            worn_before[key] = covered_now


def heal_exposure(sc, known):
    """Restore `uncovered` where this chat's history proves it was earned.

    Only where the region is bare NOW: something covering it again is the one
    state the flag must not be invented under, since the live path would have
    had its own chance to set it when that covering leaves.
    """
    changed = False
    if not isinstance(sc, dict):
        return False
    for body, entry in (sc.get("attire") or {}).items():
        regions = (entry or {}).get("regions")
        if not isinstance(regions, dict):
            continue
        for region_name in known.get(body) or ():
            region = regions.get(region_name)
            if not isinstance(region, dict):
                continue
            if _worn_garments(region) or _already_licensed(region):
                continue
            region["uncovered"] = True
            changed = True
    return changed


def muted_surfaces(sc):
    """Bare regions holding authored `beneath` prose no observer can reach.

    Reported rather than healed on its own: a region that was NEVER covered
    belongs here too and is correctly silent, so this counts the symptom and
    `heal_exposure` decides which instances of it were losses.
    """
    out = []
    if not isinstance(sc, dict):
        return out
    for body, entry in (sc.get("attire") or {}).items():
        regions = (entry or {}).get("regions")
        if not isinstance(regions, dict):
            continue
        for region_name, region in regions.items():
            if not isinstance(region, dict):
                continue
            if _worn_garments(region) or _already_licensed(region):
                continue
            if str(region.get("beneath") or "").strip():
                out.append((body, region_name))
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

def check_story(conn, chat_id, sc):
    """Invariants that span TABLES, not just the scene blob.

    The scene is one representation of the fiction; the registry, the
    derived projection and the minds are others. Where two of them answer
    the same question, they must agree -- and these are the pairs the
    architecture explicitly names as needing to stay in step.
    """
    out = []
    rooms = set((sc or {}).get("rooms") or {})
    entities = set((sc or {}).get("entities") or {})

    # An authored `size` outside the vocabulary grades as `medium` everywhere
    # and is otherwise indistinguishable from an unsized room. Reported here
    # because the grader has no channel to warn on: it is a pure function of
    # the scene, called from the middle of view composition.
    for rid, room in ((sc or {}).get("rooms") or {}).items():
        if not isinstance(room, dict):
            continue
        size = str(room.get("size") or "").strip().casefold()
        if size and size not in ROOM_SIZES:
            out.append((f"room size {size!r} is not one of "
                        f"{'/'.join(ROOM_SIZES)}; it grades as medium", rid))

    # room_registry is the cross-frame ledger of room identity; the scene is
    # the live truth. AGENTS.md: every scene writer must keep the registry
    # projection in sync.
    reg = {r["room_uid"]: r for r in conn.execute(
        "SELECT room_uid, retired_turn_id FROM room_registry WHERE chat_id=?",
        (chat_id,))}
    for rid in rooms:
        if rid not in reg:
            out.append(("live room missing from room_registry", rid))
        elif reg[rid]["retired_turn_id"] is not None:
            out.append(("live room marked retired in room_registry", rid))

    # world_entities is a DERIVED projection of the scene commit -- the one
    # divergence Phase 3a exists to prevent.
    proj = {r["entity_id"]: r for r in conn.execute(
        "SELECT entity_id, retired_turn_id FROM world_entities WHERE chat_id=?",
        (chat_id,))}
    for eid in entities:
        if eid not in proj:
            out.append(("scene entity missing from world_entities", eid))
    # The projection keeps no history: removal deletes. A stamp here means a
    # writer appeared and the entity table has started being a ledger, which
    # is room_registry's job -- reported for ANY row, not just live ones,
    # because checking only live rooms made this unfireable.
    for eid, row in proj.items():
        if row["retired_turn_id"] is not None:
            out.append(("world_entities row carries a retirement stamp the "
                        "projection has no writer for", eid))

    # A mind's records must belong to a mind this story actually has.
    attached = {r["char_id"] for r in conn.execute(
        "SELECT char_id FROM chat_chars WHERE chat_id=?", (chat_id,))}
    if attached:
        for row in conn.execute(
                "SELECT DISTINCT char_id FROM memories WHERE chat_id=?",
                (chat_id,)):
            if row["char_id"] and row["char_id"] not in attached:
                out.append(("memories held by a mind not attached to this story",
                            f"char_id={row['char_id']}"))
        for row in conn.execute(
                "SELECT DISTINCT char_id FROM relationship_events WHERE chat_id=?",
                (chat_id,)):
            if row["char_id"] and row["char_id"] not in attached:
                out.append(("relationship history for a mind not in this story",
                            f"char_id={row['char_id']}"))

    # A memory of a beat that never happened.
    last = conn.execute("SELECT MAX(idx) m FROM turns WHERE chat_id=?",
                        (chat_id,)).fetchone()["m"]
    if last is not None:
        row = conn.execute(
            "SELECT COUNT(*) n FROM memories WHERE chat_id=? AND turn_idx > ?",
            (chat_id, last)).fetchone()
        if row["n"]:
            out.append(("memories of a turn that does not exist",
                        f"{row['n']} rows past idx {last}"))
        row = conn.execute(
            "SELECT COUNT(*) n FROM memory_summaries WHERE chat_id=? "
            "AND end_turn_idx > ?", (chat_id, last)).fetchone()
        if row["n"]:
            out.append(("summary covering turns that do not exist",
                        f"{row['n']} rows past idx {last}"))

    # One story, one embedding space. A bank written in two models cannot
    # be searched coherently -- this is the banner the host sees, checked
    # at its source rather than at render time.
    models = [r["embedding_model"] for r in conn.execute(
        "SELECT DISTINCT embedding_model FROM memory_summaries "
        "WHERE chat_id=? AND embedding_model IS NOT NULL", (chat_id,))]
    if len(set(models)) > 1:
        out.append(("memory bank written in several embedding models",
                    ", ".join(sorted(set(models))[:3])))
    return out


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
    # The NEWEST story a class still appears in. A contradiction that stops
    # at an old chat is almost always a ledger that did not exist yet, not
    # a live defect -- the room registry arrived mid-corpus, and reporting
    # 140 pre-registry rooms as breakage would bury the four classes that
    # are actually still happening.
    newest = {}
    healable = []
    muted_examples = {}

    for row in rows:
        try:
            sc = json.loads(row["value"])
        except Exception:
            findings["scene will not parse"] += 1
            continue
        for kind, detail in check_scene(sc):
            findings[kind] += 1
            examples.setdefault(kind, (row["chat_id"], detail))
            newest[kind] = max(newest.get(kind, 0), row["chat_id"])
        for note in check_structure(sc):
            structure[note] += 1
            struct_examples.setdefault(note, row["chat_id"])
        for kind, detail in check_story(work, row["chat_id"], sc):
            findings[kind] += 1
            examples.setdefault(kind, (row["chat_id"], detail))
            newest[kind] = max(newest.get(kind, 0), row["chat_id"])
        probe = json.loads(json.dumps(sc))
        if heal_scene(probe):
            healable.append(row["chat_id"])
        for body, region in muted_surfaces(sc):
            muted_examples.setdefault((row["chat_id"], body, region), None)

    print("=" * 70)
    print(f"INVARIANTS — ledgers that disagree ({len(rows)} scenes)")
    print("=" * 70)
    if not findings:
        print("  none")
    latest = max((r["chat_id"] for r in rows), default=0)
    live, historical = [], []
    for kind, n in findings.most_common():
        # A class whose newest sighting is far behind the newest story is
        # a ledger that did not exist then, not something still going wrong.
        (historical if newest.get(kind, 0) < latest - 20 else live).append(kind)
    for group, label in ((live, "STILL HAPPENING"),
                         (historical, "ONLY IN OLD STORIES "
                                      "(a ledger that did not exist yet)")):
        if not group:
            continue
        print(f"\n  -- {label} --")
        for kind in group:
            cid, detail = examples[kind]
            print(f"  {findings[kind]:>5}  {kind}"
                  f"   [newest: chat {newest.get(kind, 0)}]")
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
    if muted_examples:
        # NOT presented as a defect count. A region that was never dressed
        # belongs in this list and is correctly silent; only the chat's own
        # history separates those from the ones that lost the licence, and
        # only `--heal` walks it.
        print(f"bare regions whose authored `beneath` prose is unreachable: "
              f"{len(muted_examples)} "
              f"(--heal restores the ones a chat's history proves were "
              f"uncovered in play)")
        for chat_id, body, region in sorted(muted_examples)[:8]:
            print(f"         chat {chat_id}: {body} / {region}")

    if args.heal:
        target = sqlite3.connect(args.db, timeout=30)
        target.execute("PRAGMA busy_timeout=30000")
        target.row_factory = sqlite3.Row
        healed_scenes = healed_ckpts = 0
        exposure_regions = exposure_ckpts = stripped_bodies = 0
        # PER CHAT, IN TURN ORDER, and before the per-scene repairs below:
        # this one is the only pass whose evidence is a chat's history rather
        # than a scene, so it cannot ride the loops that walk scenes in
        # whatever order the table hands them back.
        chat_ids = [r["chat_id"] for r in target.execute(
            "SELECT DISTINCT chat_id FROM world WHERE key='scene'"
            + (" AND chat_id=?" if args.chat else ""),
            (args.chat,) if args.chat else ()).fetchall()]
        for chat_id in chat_ids:
            known, worn_before = {}, {}
            pending = []
            for ck in target.execute(
                    "SELECT id, turn_idx, blob FROM checkpoints WHERE chat_id=? "
                    "ORDER BY turn_idx, id", (chat_id,)).fetchall():
                try:
                    blob = json.loads(ck["blob"])
                    sc = _scene_of(blob)
                except Exception:
                    continue
                if not isinstance(sc, dict):
                    continue
                touched = strip_state_word_garments(sc)
                observe_exposure(sc, known, worn_before)
                # Healed with what was known AS OF this turn, which is why the
                # write is deferred: `known` is still growing.
                if heal_exposure(sc, {b: set(r) for b, r in known.items()}) \
                        or touched:
                    as_str = isinstance(
                        blob.get("world", {}).get("scene"), str)
                    blob["world"]["scene"] = (
                        json.dumps(sc) if as_str else sc)
                    pending.append((ck["id"], json.dumps(blob)))
            row = target.execute(
                "SELECT value FROM world WHERE chat_id=? AND key='scene'",
                (chat_id,)).fetchone()
            live = json.loads(row["value"]) if row else None
            restored = muted = 0
            phantoms = False
            if isinstance(live, dict):
                phantoms = strip_state_word_garments(live)
                if phantoms:
                    stripped_bodies += 1
                before = len(muted_surfaces(live))
                if heal_exposure(live, known) or phantoms:
                    muted = len(muted_surfaces(live))
                    restored = before - muted
                    exposure_regions += restored
                    if not args.dry_run:
                        target.execute(
                            "UPDATE world SET value=? "
                            "WHERE chat_id=? AND key='scene'",
                            (json.dumps(live), chat_id))
            if pending and not args.dry_run:
                target.executemany(
                    "UPDATE checkpoints SET blob=? WHERE id=?",
                    [(b, i) for i, b in pending])
            exposure_ckpts += len(pending)
            if restored or phantoms:
                print(f"  chat {chat_id}: restored `uncovered` on {restored} "
                      f"region(s)"
                      + (", unwore state-word garments" if phantoms else "")
                      + f", {len(pending)} checkpoint(s)")
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
              f"{healed_scenes} scenes, {healed_ckpts} checkpoints; "
              f"exposure restored on {exposure_regions} region(s) "
              f"across {exposure_ckpts} checkpoint(s); "
              f"state-word garments unwore on {stripped_bodies} scene(s)")


if __name__ == "__main__":
    main()
