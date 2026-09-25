"""Pure identity binding and execution planning for disassembled causality.

Item handles identify things, chronology identifies spans. Neither is a world
key. A span is an atomic group of complementary patches; successive spans
must reach the domain appliers separately, before their end-state projection
loses intermediate states. No prose is interpreted here.
"""
from copy import deepcopy


_SUBJECT_MAPS = frozenset({"entities", "positions", "stations", "poses", "attire",
                          "conditions", "overlays", "vitals", "containment", "scales"})
_REFERENCE_FIELDS = frozenset({
    "entity", "entity_id", "object_id", "subject", "subject_id", "who", "actor", "target",
    "source", "source_id", "target_id", "from_id", "to_id", "holder",
    "parent_entity", "relative_to", "support", "at", "contained_by", "container",
    "wearer", "owner", "carrier", "mover", "speaker", "intended_target", "in",
})
_ROOM_FIELDS = frozenset({"room", "room_id", "to_room", "from_room", "to", "place",
                          "destination_room", "route_room", "departed_from",
                          "source_room", "speaker_room"})


def _forms(key, record):
    aliases = (record or {}).get("aliases") or []
    aliases = aliases if isinstance(aliases, list) else [aliases] if isinstance(aliases, str) else []
    return {str(s).strip().casefold() for s in
            [key, (record or {}).get("name"), *aliases]
            if s}


def _rewrite_patch(patch, entities, rooms):
    """Rewrite typed identity slots only; names and arbitrary prose stay intact."""
    def walk(value, field=""):
        if isinstance(value, dict):
            out = {}
            for key, child in value.items():
                rewritten = (entities.get(key, key) if field in _SUBJECT_MAPS
                             else rooms.get(key, key) if field == "rooms" else key)
                converted = walk(child, key)
                if field == "positions" and isinstance(converted, str):
                    converted = rooms.get(converted, converted)
                if rewritten in out and isinstance(converted, dict):
                    from world.causality import _merge_record
                    converted = _merge_record(out[rewritten], converted)
                out[rewritten] = converted
            return out
        if isinstance(value, list):
            aliases = (entities if field in {"remove_entities", "near", "targets"}
                       else rooms if field in {"remove_rooms", "interior_rooms"} else {})
            return [aliases.get(v, v) if isinstance(v, str) else walk(v, field)
                    for v in value]
        if isinstance(value, str):
            if field in _REFERENCE_FIELDS:
                return entities.get(value, rooms.get(value, value))
            if field in _ROOM_FIELDS:
                return rooms.get(value, value)
        return value
    return walk(patch)


def bind_items(transforms, scene=None):
    """Bind every item's primary record, then rewrite all cross-hand references.

    Standing keys chosen by a hand win, then a unique exact standing name,
    then the first minted key. Entity and room namespaces are separate: an
    object's interior is not its entity. A multi-room topology patch does not
    claim that every room it touches is the same room.
    """
    rows = deepcopy(list(transforms))
    groups = {}
    for row in rows:
        groups.setdefault(str(row.get("item_id") or 0), []).append(row)
    aliases = {"entity": {}, "room": {}}
    bindings, notes = {}, []
    for item, changes in groups.items():
        names = {str(r.get("object_name") or "").strip().casefold()
                 for r in changes} - {""}
        for kind, channel in (("entity", "entities"), ("room", "rooms")):
            standing = dict((scene or {}).get(channel) or {})
            if kind == "entity":
                # Registered bodies need not have an entities row. Their
                # standing identity must still beat an operation's object_id.
                for field in ("positions", "attire", "scales"):
                    for key in (scene or {}).get(field) or {}:
                        standing.setdefault(key, {})
            named_standing = [key for key, record in standing.items()
                              if isinstance(record, dict) and _forms(key, record) & names]
            def standing_keys(reference):
                if reference in standing:
                    return [reference]
                folded = str(reference).strip().casefold()
                return [key for key, record in standing.items()
                        if isinstance(record, dict) and folded in _forms(key, record)]
            candidates = []
            # Which candidates the item's own NAME vouches for, and which are
            # only the singleton fallback's guess. An item may legitimately
            # touch two things -- turning a key in a lock patches the lock --
            # so a sibling transform's unnamed record must never decide what
            # the item IS. See the filter below.
            named_candidates, guessed = set(), set()
            for row in changes:
                records = (row.get("patch") or {}).get(channel) or {}
                records = records if isinstance(records, dict) else {}
                for key, record in records.items():
                    if not isinstance(record, dict):
                        continue
                    if kind == "room" and record.get("parent_entity"):
                        continue
                    matches = bool(_forms(key, record) & names)
                    # A singleton related record is not evidence that a
                    # standing actor acquired that object's identity.
                    fallback = (kind == "entity" and len(records) == 1
                                and not (named_standing and record.get("name")))
                    if matches or fallback:
                        if key not in candidates:
                            candidates.append(key)
                        if matches:
                            named_candidates.add(key)
                        else:
                            guessed.add(key)
                if kind == "entity":
                    operations = (row.get("patch") or {}).get("inventory_ops") or []
                    for op in operations if isinstance(operations, list) else []:
                        key = op.get("object_id") if isinstance(op, dict) else None
                        if isinstance(key, str) and key and key not in candidates:
                            candidates.append(key)
                    removals = (row.get("patch") or {}).get("remove_entities") or []
                    for key in removals if isinstance(removals, list) else []:
                        if isinstance(key, str) and key and key not in candidates:
                            candidates.append(key)
            if not candidates:
                if kind == "entity":
                    for row in changes:
                        for field in ("positions", "stations", "poses", "containment", "scales", "vitals"):
                            table = (row.get("patch") or {}).get(field) or {}
                            if not isinstance(table, dict):
                                continue
                            if len(table) == 1:
                                key = next(iter(table))
                                record = ((scene or {}).get("entities") or {}).get(key) or {}
                                if _forms(key, record) & names and key not in candidates:
                                    candidates.append(key)
                if not candidates:
                    continue
            # A NAMED CANDIDATE BEATS A GUESSED ONE, and this is the whole of
            # the repair. Measured live (the owner's chat 151, 2026-09-20): the
            # author gave a beat two handles -- 2 "key", 3 "The TARDIS" -- and
            # item 2 carried two rows, one MINTING the key ("fishes the key from
            # his coat pocket") and one PATCHING the lock ("turns the key in the
            # TARDIS lock"). The mint's record was vouched for by name; the
            # lock's was a bare `{"state": ...}` admitted only by `fallback`.
            # With no standing `key` to anchor it, `held` below then preferred
            # the candidate that was already a world record -- the ship -- and
            # aliased the freshly minted key onto it. The Doctor ended up
            # holding the TARDIS, the ship wore the key's description, and
            # nobody could walk into a thing somebody was carrying.
            #
            # ONE ITEM IS ONE RECORD; one item's ROWS may act on several. The
            # fallback exists for an item whose record nothing names, and it
            # keeps that job: this only stops it outvoting a record the item's
            # own name vouches for.
            if named_candidates and guessed:
                # ...AND ONLY WHERE THE GUESS IS ALREADY A WORLD RECORD. That
                # is the whole of the harm: `held` below prefers a candidate the
                # world already holds, so a standing record admitted by the
                # fallback CAPTURES the item and the named mint is aliased onto
                # it. A guess that names nothing standing cannot capture
                # anything, and it is the ordinary continuation -- "Mara opens
                # the box" then "Mara shuts the box", the second transform
                # written tersely with no name (`test_causal_program`'s
                # partial-entity case, which this broke when the rule was
                # written without this clause).
                dropped = [key for key in candidates if key in guessed
                           and key not in named_candidates
                           and standing_keys(key)]
                if dropped:
                    notes.append({
                        "item_id": item, "kind": kind,
                        "reason": "a sibling transform's unnamed record does "
                                  "not decide what this item is",
                        "keys": dropped})
                    candidates = [key for key in candidates if key not in dropped]
            if named_standing:
                # A transfer filed under its actor touches a different object;
                # it does not rename that object to the actor or vice versa.
                unrelated = [key for key in candidates
                             if standing_keys(key)
                             and not set(standing_keys(key)) <= set(named_standing)]
                if unrelated:
                    notes.append({"item_id": item,
                                  "reason": "related world keys are not item aliases",
                                  "kind": kind, "keys": unrelated})
                candidates = [key for key in candidates if key not in unrelated]
                if not candidates:
                    continue
            held = list(dict.fromkeys(key for candidate in candidates
                                      for key in standing_keys(candidate)))
            if not held:
                held = named_standing
            if len(held) > 1:
                notes.append({"item_id": item, "reason": "ambiguous standing identity",
                              "kind": kind, "keys": held})
                continue
            canonical = held[0] if held else candidates[0]
            bindings.setdefault(item, {})[kind] = canonical
            for key in candidates:
                prior = aliases[kind].get(key)
                if prior is not None and prior != canonical:
                    notes.append({"item_id": item, "reason": "world key claimed by several items",
                                  "kind": kind, "keys": [key, prior, canonical]})
                    continue
                aliases[kind][key] = canonical
            # A co-owner may address the exact item name rather than the key
            # minted by its sibling. Only unambiguous names are rewritten.
            for row in changes:
                name = str(row.get("object_name") or "").strip()
                if name and sum(name.casefold() in {
                        str(r.get("object_name") or "").strip().casefold()
                        for r in other} for other in groups.values()) == 1:
                    aliases[kind][name] = canonical
    for row in rows:
        row["patch"] = _rewrite_patch(row.get("patch") or {},
                                      aliases["entity"], aliases["room"])
    return rows, bindings, notes


def fold_steps(steps):
    """Compatibility projection for readers that ask only for the last state."""
    from world.causality import _merge_channel
    out = {}
    for step in steps:
        for channel, value in (step.get("patch") or {}).items():
            if channel != "causal_steps":
                _merge_channel(out, channel, value)
    return out


def event_worlds(worlds, events):
    """Map the perception stream to its actual before-span worlds by event id.

    Current causal streams name their stage and span, so several outcomes of
    one declaration keep distinct moments. Archived declaration-only streams
    use the first cited span. Unknown/background events retain the caller's
    final-world fallback. Never match event prose or guess an actor's move.
    """
    by_event, by_span = {}, {}
    for world in worlds or []:
        if world.get("stage") and world.get("chrono_id") is not None:
            by_span[(str(world["stage"]), str(world["chrono_id"]))] = world["before"]
        for event in world.get("events") or []:
            if event and not event.endswith(":raw"):
                by_event.setdefault(str(event), world["before"])
    mapped = {}
    for index, entry in enumerate(events):
        source = entry.get("event") or {}
        span = entry.get("causal_span") or source.get("_causal_span")
        if isinstance(span, (list, tuple)) and tuple(map(str, span)) in by_span:
            mapped[index] = by_span[tuple(map(str, span))]
            continue
        keys = [entry.get("declared"), source.get("event_id")]
        for key in keys:
            if str(key or "") in by_event:
                mapped[index] = by_event[str(key)]
                break
    return mapped


def program_from_history(history, ledgers=(), stage="resolve", requirements=()):
    """Group all hands and all items by span, including spans with no writes."""
    groups = {}
    for row in ledgers:
        chrono = int(row.get("chrono_id") or row.get("event_id") or 0)
        if chrono > 0:
            groups[chrono] = {"chrono_id": chrono, "stage": stage, "events": [
                str(v) for v in (row.get("event_id"), row.get("source_event_id"),
                                row.get("from_declaration")) if v], "patch": {},
                              "transforms": []}
    from world.causality import _merge_channel
    for row in history:
        chrono = int(row["chrono_id"])
        step = groups.setdefault(chrono, {"chrono_id": chrono, "stage": stage,
                                          "events": [], "patch": {}, "transforms": []})
        step["transforms"].append(deepcopy(row))
        for channel, value in row["patch"].items():
            _merge_channel(step["patch"], channel, value)
    for requirement in requirements:
        chrono = int(requirement["chrono_id"])
        if chrono in groups:
            groups[chrono].setdefault("requirements", []).append(deepcopy(requirement))
    return [groups[key] for key in sorted(groups)]


def _content(value):
    """Provenance is engine metadata, not a change to a domain record."""
    if isinstance(value, dict):
        return {k: _content(v) for k, v in value.items()
                if k not in {"from_event", "source_event_id", "phase_sources"}}
    if isinstance(value, list):
        return [_content(v) for v in value]
    return value


def program_steps(diff):
    """Reconcile deterministic edits into the executable program.

    A removed map key is refused throughout; a corrected record replaces its
    last write. Operation lists are matched with multiplicity, so removed ops
    never replay and surviving duplicates still execute twice. New engine
    writes land in a final step. Explicit blocked spans are handled *before*
    this projection comparison by ``prune_program``.
    """
    steps = deepcopy(diff.get("causal_steps") or [])
    if not steps:
        return []
    baseline = fold_steps(steps)
    residual = {k: deepcopy(v) for k, v in diff.items()
                if k not in {"causal_steps", "phase_sources"}}
    from world.causality import LIST_MAP_CHANNELS, ATOMIC_CHANNELS
    for channel, old in baseline.items():
        if channel == "phase_sources":
            continue
        new = residual.pop(channel, None)
        occurrences = [s["patch"] for s in steps if channel in s.get("patch", {})]
        if isinstance(old, dict) and channel not in ATOMIC_CHANNELS:
            new = new if isinstance(new, dict) else {}
            for key in old:
                places = [p[channel] for p in occurrences if key in p[channel]]
                if key not in new:
                    for table in places:
                        table.pop(key, None)
                elif channel in LIST_MAP_CHANNELS:
                    remaining = list(new[key] or [])
                    for table in places:
                        table[key] = _surviving_rows(table[key], remaining)
                    if remaining:
                        places[-1][key].extend(deepcopy(remaining))
                elif _content(old[key]) != _content(new[key]):
                    places[-1][key] = deepcopy(new[key])
            extra = {k: v for k, v in new.items() if k not in old}
            if extra:
                residual[channel] = extra
        elif isinstance(old, list):
            remaining = list(new or [])
            for patch in occurrences:
                patch[channel] = _surviving_rows(patch[channel], remaining)
            if remaining:
                residual[channel] = remaining
        elif new is None:
            for patch in occurrences:
                patch.pop(channel, None)
        elif _content(old) != _content(new):
            occurrences[-1][channel] = deepcopy(new)
    if any(residual.values()):
        steps.append({"stage": "engine", "chrono_id": 0, "events": [],
                      "patch": residual})
    return steps


def _surviving_rows(rows, remaining):
    kept = []
    for row in rows:
        match = next((i for i, candidate in enumerate(remaining)
                      if _content(candidate) == _content(row)), None)
        if match is not None:
            kept.append(deepcopy(remaining.pop(match)))
    return kept


def prune_program(diff, blocked):
    """Remove blocked spans then regenerate their projection, preserving guards."""
    steps = program_steps(diff)
    kept, dropped = [], []
    for step in steps:
        ids = set(step.get("events") or [])
        # Raw chronological numbers are local to one invocation. Once both
        # invocations are present, phase ids (the event aliases) disambiguate.
        if len({s.get("stage") for s in steps if s.get("stage") != "engine"}) <= 1:
            ids.add(str(step.get("chrono_id") or ""))
        if ids & blocked:
            dropped.extend((channel, sorted(ids & blocked)[0])
                           for channel in step.get("patch") or {})
        else:
            kept.append(step)
    diff.clear()
    diff.update(fold_steps(kept))
    diff["causal_steps"] = kept
    return dropped
