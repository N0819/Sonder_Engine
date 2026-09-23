"""Read-only receipts for typed causal effects at their chronological span.

A model's completion label is not evidence. These checks compare its desired
postconditions with the world the domain appliers actually produced. They do
not infer a missing operation from prose or turn an ignored operation into a
successful no-op. Channels whose effects live outside a scene remain explicit
unresolved receipts until their own commit boundary can verify them.
"""

from copy import deepcopy


_META = frozenset({"from_event", "source_event_id", "unasserted", "phase_sources"})
_MISSING = object()
_AMBIGUOUS = object()


def _without_metadata(value):
    if isinstance(value, dict):
        return {k: _without_metadata(v) for k, v in value.items() if k not in _META}
    if isinstance(value, list):
        return [_without_metadata(v) for v in value]
    return value


def _subset(desired, actual):
    """Only requested fields decide completion; provenance never does."""
    desired = _without_metadata(desired)
    if isinstance(desired, dict):
        return isinstance(actual, dict) and all(
            key in actual and _subset(value, actual[key])
            for key, value in desired.items())
    return desired == _without_metadata(actual)


def _same(scene, left, right):
    from world.spatial import canonical_subject
    return bool(left and right) and (
        canonical_subject(scene, left).casefold()
        == canonical_subject(scene, right).casefold())


def _record(scene, channel, subject):
    table = scene.get(channel) or {}
    if not isinstance(table, dict):
        return _MISSING
    matches = [value for key, value in table.items() if _same(scene, key, subject)]
    return matches[0] if len(matches) == 1 else _AMBIGUOUS if matches else _MISSING


def _known(scene, subject):
    """Whether the scene holds `subject`: an entity, a body in a ledger, or
    one room's own fixture.

    A FIXTURE IS AN ENDPOINT HERE AS IT IS AT THE MERGE
    (`spatial_contacts._anchor_room_of`). This reader left it out, so every
    contact with a fixture -- a palm on a dock, hands on a lever -- verified
    as "lacks established endpoints", the act that made it counted as refused
    by the world, and perception un-saw the act whole: a sluice tender
    working the jack in plain view of the yard and the woman watching him
    braced on the dock, both invisible (playerless Aldermill round 4 replay,
    2026-09-23)."""
    from world.spatial import _anchor_room_of, _unique_entity_keyed
    key, _ = _unique_entity_keyed(scene, subject)
    return bool(key) or any(_record(scene, channel, subject) is not _MISSING
                            for channel in ("positions", "attire", "scales")) \
        or _anchor_room_of(scene, subject) is not None


def _receipt(channel, target, satisfied, prior, *, code="postcondition_missing",
             reason="The requested state is absent after this span.", **extra):
    result = {"channel": channel, "target": target,
              "status": "unchanged" if satisfied and prior else
                        "applied" if satisfied else "unresolved"}
    if not satisfied:
        result.update(code=code, reason=reason)
    result.update(extra)
    return result


def _unresolved(channel, target, code, reason, **extra):
    return _receipt(channel, target, False, False, code=code, reason=reason, **extra)


def _map_receipts(before, after, channel, changes, context=None):
    from world.spatial import _unique_entity_keyed, room_of, scene_room_id
    if not isinstance(changes, dict) or not changes:
        return [_unresolved(channel, "", "missing_desired_state",
                            "A nonempty desired state is required.")]
    out = []
    for subject, desired in changes.items():
        desired = _without_metadata(desired)
        if desired == {}:
            out.append(_unresolved(channel, subject, "missing_desired_state",
                                   "Metadata or an empty record proves no effect."))
            continue
        if channel == "entities":
            get = lambda world: _unique_entity_keyed(world, subject)[1]
            valid = isinstance(desired, dict)
            check = lambda world: bool(get(world)) and _subset(desired, get(world))
        elif channel == "positions":
            destination = scene_room_id(after, desired)
            valid = bool(destination) and _known(after, subject)
            check = lambda world: room_of(world, subject) == destination
        elif channel == "containment":
            valid = _known(after, subject) or (desired is None and _known(before, subject))
            if desired is None:
                check = lambda world: _record(world, "contained", subject) is _MISSING
            else:
                from world.spatial import _clean_containment
                expected = _clean_containment(desired, subject)
                valid = valid and bool(expected) and _known(after, expected["in"])
                def check(world, expected=expected, subject=subject):
                    actual = _record(world, "contained", subject)
                    return bool(expected) and isinstance(actual, dict) and (
                        _same(world, actual.get("in"), expected["in"])
                        and actual.get("mode") == expected["mode"])
        elif channel == "stations":
            valid = _known(after, subject) and isinstance(desired, dict)
            def check(world):
                actual = _record(world, channel, subject)
                if not isinstance(actual, dict):
                    return False
                direct = {key: value for key, value in desired.items() if key != "near"}
                if not _subset(direct, actual):
                    return False
                if "near" not in desired:
                    return True
                if not isinstance(desired["near"], list):
                    return False
                expected = list(desired["near"])
                if any(not _known(world, other) or room_of(world, other) != room_of(world, subject)
                       for other in expected):
                    return False
                # Proximity is a symmetric graph. A local near:[] replaces
                # this row, not the reverse rows; explicit reverse clears
                # are required to remove those edges. Read the original
                # records plus the other requested station writes, never
                # infer a desired edge from the after-world being checked.
                sources = deepcopy(before.get("stations") or {})
                for who, station in ((context or {}).get("stations") or {}).items():
                    if isinstance(station, dict):
                        sources[who] = {**(sources.get(who) or {}), **station}
                for other, station in sources.items():
                    if _same(world, other, subject) or not isinstance(station, dict):
                        continue
                    if room_of(world, other) != room_of(world, subject):
                        continue
                    if any(_same(world, name, subject) for name in station.get("near") or []):
                        expected.append(other)
                actual_near = actual.get("near") or []
                return (all(any(_same(world, a, e) for a in actual_near) for e in expected)
                        and all(any(_same(world, a, e) for e in expected) for a in actual_near))
        else:
            valid = _known(after, subject) and isinstance(desired, dict)
            check = lambda world: _subset(desired, _record(world, channel, subject))
        if not valid:
            out.append(_unresolved(channel, subject, "invalid_or_missing_target",
                                   "The desired state or its world target is not established."))
        else:
            out.append(_receipt(channel, subject, check(after), check(before)))
    return out


def _removal_receipts(before, after, channel, changes):
    from world.spatial import _unique_entity_keyed
    if not isinstance(changes, list) or not changes:
        return [_unresolved(channel, "", "missing_desired_state",
                            "A removal must identify an established target.")]
    out = []
    for target in changes:
        if channel == "remove_entities":
            exists = lambda world: bool(_unique_entity_keyed(world, target)[0])
        else:
            exists = lambda world: target in (world.get("rooms") or {})
        if not exists(before) and not exists(after):
            out.append(_unresolved(channel, target, "unknown_removal_target",
                                   "Neither world establishes the removal target."))
        else:
            out.append(_receipt(channel, target, not exists(after), not exists(before)))
    return out


def _room_record(scene, target):
    from world.spatial import scene_room_id
    key = scene_room_id(scene, target)
    return (scene.get("rooms") or {}).get(key) if key else None


def _rooms_receipts(before, after, changes):
    """Read the partial room/edge contract, including the shared passage."""
    from world.spatial import (_ROOM_SILENT_WHEN_EMPTY, normalize_barrier,
                               resolve_edge, scene_room_id)
    if not isinstance(changes, dict) or not changes:
        return [_unresolved("rooms", "", "missing_desired_state", "A desired room change is required.")]
    out = []
    for target, raw in changes.items():
        if not isinstance(raw, dict):
            out.append(_unresolved("rooms", target, "invalid_operation", "A room change must be an object."))
            continue
        desired = _without_metadata(raw)
        direct = {key: value for key, value in desired.items()
                  if key not in {"adjacent", "remove_anchors"}
                  and not (key in _ROOM_SILENT_WHEN_EMPTY and not value)
                  and not (key in {"name", "desc", "notes", "parent_entity"} and not value)}
        edges = desired.get("adjacent") or []
        removals = desired.get("remove_anchors") or []
        if not direct and not edges and not removals:
            out.append(_unresolved("rooms", target, "missing_desired_state", "An empty room restatement proves no effect."))
            continue
        valid = isinstance(edges, list) and isinstance(removals, list) and all(
            isinstance(edge, dict) and edge.get("to") for edge in edges)
        def check(world):
            room = _room_record(world, target)
            if not isinstance(room, dict) or not _subset(direct, room):
                return False
            anchors = room.get("anchors") or {}
            if any(str(key).casefold() == str(removed).casefold()
                   for key in anchors for removed in removals):
                return False
            for wanted in edges:
                destination = scene_room_id(world, wanted["to"])
                if not destination:
                    return False
                standing = [resolve_edge(world, edge) for edge in room.get("adjacent") or []
                            if isinstance(edge, dict) and scene_room_id(world, edge.get("to")) == destination]
                if len(standing) != 1:
                    return False
                for field, value in _without_metadata(wanted).items():
                    if field == "to" or value is None or value == "":
                        continue
                    actual = standing[0].get(field, _MISSING)
                    if field == "barrier":
                        if actual is _MISSING or normalize_barrier(value) != normalize_barrier(actual):
                            return False
                    elif not _subset(value, actual):
                        return False
            return True
        out.append(_receipt("rooms", target, valid and check(after), valid and check(before)))
    return out


def _adjacency_removal_receipts(before, after, changes):
    from world.spatial import scene_room_id
    out = []
    for index, raw in enumerate(changes if isinstance(changes, list) else []):
        source, target = (raw.get("room"), raw.get("to")) if isinstance(raw, dict) else (None, None)
        valid = bool(source and target and (_room_record(before, source) or _room_record(after, source))
                     and (_room_record(before, target) or _room_record(after, target)))
        def check(world):
            for left, right in ((source, target), (target, source)):
                room = _room_record(world, left) or {}
                right_id = scene_room_id(world, right)
                if any(isinstance(edge, dict) and scene_room_id(world, edge.get("to")) == right_id
                       for edge in room.get("adjacent") or []):
                    return False
            return True
        out.append(_receipt("remove_adjacent", source or "", valid and check(after),
                            valid and check(before), operation=index))
    return out or [_unresolved("remove_adjacent", "", "missing_desired_state", "An edge removal needs two rooms.")]


def _scale_receipts(before, after, changes):
    from world.spatial import clamp_scale, scale_of
    if not isinstance(changes, dict) or not changes:
        return [_unresolved("scales", "", "missing_desired_state", "A desired relative scale is required.")]
    out = []
    for target, value in changes.items():
        factor = clamp_scale(value)
        valid = factor is not None and (_known(before, target) or any(
            _record(after, channel, target) is not _MISSING
            for channel in ("positions", "attire", "entities")))
        out.append(_receipt("scales", target, valid and scale_of(after, target) == factor,
                            valid and scale_of(before, target) == factor))
    return out


def _destruction_receipts(before, after, desired):
    """Verify local removal; a regional book cascade needs its own receipt."""
    from world.spatial import _unique_entity_keyed
    if not isinstance(desired, dict) or not desired.get("target_id"):
        return [_unresolved("destruction", "", "invalid_operation", "Destruction needs an established target.")]
    target = desired["target_id"]
    scale = str(desired.get("scale") or "").strip().casefold()
    if scale == "region":
        return [_unresolved("destruction", target, "unsupported_postcondition",
                            "A regional destruction needs the book and room-registry cascade receipt.")]
    if scale not in {"vehicle", "building"} or not _unique_entity_keyed(before, target)[0]:
        return [_unresolved("destruction", target, "invalid_or_missing_target",
                            "The scene does not establish this vehicle/building destruction target.")]
    rooms = {key for key, room in (before.get("rooms") or {}).items()
             if isinstance(room, dict) and _same(before, room.get("parent_entity"), target)}
    def check(world):
        return (not _unique_entity_keyed(world, target)[0]
                and not rooms.intersection(world.get("rooms") or {})
                and not rooms.intersection((world.get("positions") or {}).values()))
    # This certifies only scene removal. Retirement of off-scene records and
    # destruction news remain a commit-side obligation, never inferred here.
    return [_receipt("destruction", target, check(after), check(before), scope="scene"),
            _unresolved("destruction", target, "pending_commit_domain",
                        "Book retirement, room registry and destruction news require commit receipts.", scope="commit")]


def _scalar_receipts(before, after, channel, desired):
    """Read carried scene labels; a declared patch is never its own proof."""
    if not isinstance(desired, str) or not desired.strip():
        return [_unresolved(channel, "", "missing_desired_state", "A nonempty scene label is required.")]
    expected = desired.strip()
    field = "time_of_day" if channel == "time" else channel
    return [_receipt(channel, field, after.get(field) == expected, before.get(field) == expected)]


def _weather_receipts(before, after, desired):
    from world.weather import (AIRS, CLOUDS, FALL_KINDS, INTENSITIES, WINDS,
                               TEMPERATURES, DRIFT_STEP_KEY, _resolve, normalize_weather)
    if not isinstance(desired, dict) or not desired:
        return [_unresolved("weather", "", "missing_desired_state", "A nonempty typed weather record is required.")]
    desired = _without_metadata(desired)
    if not desired:
        return [_unresolved("weather", "", "missing_desired_state", "Weather provenance alone proves no effect.")]
    axes = {"air": AIRS, "cloud": CLOUDS, "precipitation_kind": FALL_KINDS,
            "intensity": INTENSITIES, "wind": WINDS, "temperature": TEMPERATURES}
    known = set(axes) | {"sky", "precipitation", "electrical", "thundersnow"}
    invalid = set(desired) - known
    invalid.update(key for key, choices in axes.items() if key in desired
                   and _resolve(desired[key], choices, key) is None)
    invalid.update(key for key in ("electrical", "thundersnow") if key in desired
                   and not isinstance(desired[key], bool))
    invalid.update(key for key in ("sky", "precipitation") if key in desired
                   and (not isinstance(desired[key], str) or not desired[key].strip()))
    if invalid:
        return [_unresolved("weather", "", "invalid_desired_state",
                            "Unrecognized weather fields or values cannot prove a change.", fields=sorted(invalid))]
    expected = normalize_weather(desired, before.get("weather"))
    expected.pop(DRIFT_STEP_KEY, None)
    def check(world):
        actual = world.get("weather")
        return isinstance(actual, dict) and bool(actual) and _subset(expected, actual)
    return [_receipt("weather", "weather", check(after), check(before))]


def _time_receipts(before, after, desired):
    from math import isfinite
    from world.mechanics import TIME_METADATA_KEYS
    if isinstance(desired, str):
        return _scalar_receipts(before, after, "time", desired)
    if not isinstance(desired, dict) or not desired:
        return [_unresolved("time", "", "missing_desired_state", "An explicit time label or clock endpoint is required.")]
    # Current scene snapshots normally carry no clock: it is committed in a
    # separate domain. Never substitute the desired endpoint or a duration
    # calculation for that missing authoritative observation.
    endpoints = {key: value for key, value in desired.items()
                 if key in {"end_seconds", "elapsed_seconds"}}
    unsupported = set(desired) - set(endpoints) - TIME_METADATA_KEYS
    out = []
    if unsupported:
        out.append(_unresolved("time", "simulation_clock", "unsupported_postcondition",
                               "This time claim needs its authoritative clock-span receipt.", fields=sorted(unsupported)))
    if not endpoints:
        return out or [_unresolved("time", "", "missing_desired_state",
                                   "A passage phrase or clock metadata is not a requested time-of-day label.")]
    for field, value in endpoints.items():
        valid = isinstance(value, (int, float)) and not isinstance(value, bool) and isfinite(value)
        def check(world):
            clock = world.get("simulation_clock")
            actual = clock.get("elapsed_seconds") if isinstance(clock, dict) else None
            return (valid and isinstance(actual, (int, float)) and not isinstance(actual, bool)
                    and isfinite(actual) and actual == value)
        out.append(_receipt("time", "simulation_clock", check(after), check(before), field=field))
    return out


def _inventory_receipts(before, after, changes, patch):
    from world.spatial import (_anchor_for_entity, _unique_entity_keyed,
                               resolve_placement_target, room_of)
    out = []
    for index, operation in enumerate(changes if isinstance(changes, list) else []):
        if not isinstance(operation, dict):
            out.append(_unresolved("inventory_ops", "", "invalid_operation",
                                   "An inventory operation must be an object.", operation=index))
            continue
        target = operation.get("object_id") or ""
        key, entity = _unique_entity_keyed(after, target)
        kind, destination = resolve_placement_target(after, operation.get("to_id"))
        relation = str(operation.get("relation") or "carried").strip().casefold()
        holder = _unique_entity_keyed(after, destination)[1] if destination else {}
        carry = kind in {"carrier", "vouched"} or (
            kind == "anchor" and (relation == "mounted" or (
                holder.get("container") is True and relation in {"inside", "container", "pocket"})))
        if not key or not kind or entity.get("ubiquitous") or _same(after, target, destination):
            out.append(_unresolved("inventory_ops", target, "invalid_or_missing_target",
                                   "The transferred object or destination is not established.",
                                   operation=index))
            continue
        room = destination if kind == "room" else room_of(after, destination)
        anchor = _anchor_for_entity(after, room, destination) if kind == "anchor" and not carry else None
        known_garment = any(_known_garment(world, target) for world in (before, after))
        def check(world):
            actual = _record(world, "contained", target)
            if carry:
                return isinstance(actual, dict) and (
                    _same(world, actual.get("in"), destination)
                    and actual.get("mode") == ("container" if relation == "interior" else relation)
                    and bool(room) and room_of(world, target) == room
                    and (relation != "worn" or not known_garment
                         or _wardrobe_has_object(world, destination, target)))
            if actual is not _MISSING or not room or room_of(world, target) != room:
                return False
            if kind == "anchor":
                station = _record(world, "stations", target)
                return bool(anchor) and isinstance(station, dict) and station.get("at") == anchor
            return True
        def cleanup_holds(world):
            from world.spatial import bearing_contact_holder, scene_names_body
            def free_holder(who):
                return carry and relation in {"held", "carried"} and _same(world, who, destination)
            for contact in world.get("contacts") or []:
                previous = bearing_contact_holder(world, contact, target)
                if not previous or free_holder(previous):
                    continue
                reasserted = any(isinstance(op, dict) and op.get("op", "add") == "add"
                                 and _contact_matches(world, op, contact, exact_parts=True)
                                 for op in patch.get("contact_ops") or [])
                if not reasserted:
                    return False
            _, record = _unique_entity_keyed(world, target)
            state = record.get("state") if isinstance(record.get("state"), dict) else {}
            held_by = record.get("held_by") or state.get("held_by")
            if held_by and not free_holder(held_by):
                return False
            for who, entity in (world.get("entities") or {}).items():
                state = entity.get("state") if isinstance(entity, dict) else None
                held = state.get("held_items") if isinstance(state, dict) else None
                if isinstance(held, list) and not free_holder(who) and any(
                        _same(world, name, target) for name in held):
                    return False
            pose = _record(world, "poses", target)
            if isinstance(pose, dict) and pose.get("support") and scene_names_body(world, pose["support"]) \
                    and not free_holder(pose["support"]):
                return False
            for wearer in world.get("attire") or {}:
                if any(_same(world, garment, target) for garment in _worn(world, wearer)) and not (
                        carry and relation == "worn" and _same(world, wearer, destination)):
                    return False
            return True
        out.append(_receipt("inventory_ops", target,
                            check(after) and cleanup_holds(after),
                            check(before) and cleanup_holds(before), operation=index))
    return out or [_unresolved("inventory_ops", "", "missing_desired_state",
                               "A nonempty typed transfer is required.")]


def _contact_matches(scene, desired, actual, *, exact_parts=False):
    if not isinstance(actual, dict):
        return False
    for mirrored in (False, True):
        left, right = ("target", "actor") if mirrored else ("actor", "target")
        if not (_same(scene, desired.get("actor"), actual.get(left)) and
                _same(scene, desired.get("target"), actual.get(right))):
            continue
        if all((not exact_parts and not desired.get(key + "_part")) or
                            str(desired.get(key + "_part") or "").casefold() ==
                            str(actual.get(side + "_part") or "").casefold()
                            for key, side in (("actor", left), ("target", right))):
            return True
    return False


def _contact_receipts(before, after, changes):
    out = []
    for index, raw in enumerate(changes if isinstance(changes, list) else []):
        if not isinstance(raw, dict):
            out.append(_unresolved("contact_ops", "", "invalid_operation",
                                   "A contact operation must be an object.", operation=index))
            continue
        operation = str(raw.get("op") or "add").casefold()
        target = raw.get("target") or raw.get("actor") or ""
        if operation == "clear":
            actor = raw.get("actor")
            valid = not actor or _known(after, actor) or _known(before, actor)
            def check(world):
                return not any(not actor or _same(world, actor, c.get("actor")) or
                               _same(world, actor, c.get("target"))
                               for c in world.get("contacts") or [] if isinstance(c, dict))
        elif operation == "remove":
            valid = all(_known(after, raw.get(side)) or _known(before, raw.get(side))
                        for side in ("actor", "target"))
            check = lambda world: not any(_contact_matches(world, raw, c)
                                         for c in world.get("contacts") or [])
        elif operation in {"add", "cross"}:
            desired = {k: v for k, v in raw.items()
                       if k not in _META | {"op", "crossed_target_part"}}
            valid = _known(after, raw.get("actor")) and _known(after, raw.get("target"))
            if operation == "cross":
                source = {**raw, "target_part": raw.get("crossed_target_part")}
                valid = valid and bool(raw.get("crossed_target_part")) and bool(raw.get("target_interior"))
                valid = valid and sum(_contact_matches(before, source, c)
                                      and c.get("relation") == "interior"
                                      for c in before.get("contacts") or []) == 1
                desired.update(relation="interior", motion="moving", target_part=raw.get("target_part", ""))
            def check(world, desired=desired):
                fields = {k: v for k, v in desired.items()
                          if k not in {"actor", "target", "actor_part", "target_part"}}
                return any(_contact_matches(world, desired, c, exact_parts=True) and _subset(fields, c)
                           for c in world.get("contacts") or [])
        else:
            valid = False
        if not valid:
            out.append(_unresolved("contact_ops", target, "invalid_or_missing_target",
                                   "The contact lacks established endpoints or a valid transition.",
                                   operation=index))
        else:
            out.append(_receipt("contact_ops", target, check(after), check(before), operation=index))
    return out or [_unresolved("contact_ops", "", "missing_desired_state",
                               "A nonempty typed contact operation is required.")]


def _garment_name(value):
    return str(value.get("name") or value.get("item") or "") if isinstance(value, dict) else str(value)


def _worn(scene, wearer):
    entry = _record(scene, "attire", wearer)
    if not isinstance(entry, dict):
        return []
    values = [_garment_name(value) for value in entry.get("wearing") or []]
    for region in (entry.get("regions") or {}).values():
        for garment in (region.get("garments") or []) if isinstance(region, dict) else []:
            if isinstance(garment, dict) and garment.get("state") != "removed":
                name = _garment_name(garment)
                if name and name not in values:
                    values.append(name)
    return values


def _wardrobe_has_object(scene, wearer, subject):
    """A wardrobe name must uniquely identify this actual object."""
    from world.spatial import _unique_entity_keyed
    target, _ = _unique_entity_keyed(scene, subject)
    return bool(target) and any(_unique_entity_keyed(scene, garment)[0] == target
                                for garment in _worn(scene, wearer))


def _known_garment(scene, subject):
    from world.spatial import _unique_entity_keyed
    _, entity = _unique_entity_keyed(scene, subject)
    state = entity.get("state") if isinstance(entity.get("state"), dict) else {}
    return bool(state.get("clothing") is True or state.get("garment")
                or any(_wardrobe_has_object(scene, wearer, subject)
                       for wearer in scene.get("attire") or {}))


def _attire_receipts(before, after, changes):
    if not isinstance(changes, dict) or not changes:
        return [_unresolved("attire", "", "missing_desired_state", "A desired wardrobe change is required.")]
    out = []
    for wearer, raw in changes.items():
        desired = _without_metadata(raw)
        if isinstance(desired, dict):
            # Schema defaults are silence, except an explicit empty complete
            # wearing/replace snapshot, which requests an empty wardrobe.
            desired = {k: v for k, v in desired.items() if v is not None and
                       (v not in ({}, []) or k in {"wearing", "replace", "state"})}
        if not isinstance(desired, dict) or not desired or not _known(after, wearer):
            out.append(_unresolved("attire", wearer, "invalid_or_missing_target",
                                   "A desired change and established wearer are required."))
            continue
        unsupported = set(desired) - {"wearing", "replace", "add", "remove", "state", "regions"}
        if unsupported:
            out.append(_unresolved("attire", wearer, "unsupported_postcondition",
                                   "This wardrobe field needs a domain-specific verifier.",
                                   fields=sorted(unsupported)))
        def check(world):
            wearing = _worn(world, wearer)
            for key in ("wearing", "replace"):
                if desired.get(key) is not None and [
                        _garment_name(value) for value in desired[key]] != wearing:
                    return False
            if any(not any(_same(world, _garment_name(value), name) for name in wearing)
                   for value in desired.get("add") or []):
                return False
            if any(any(_same(world, _garment_name(value), name) for name in wearing)
                   for value in desired.get("remove") or []):
                return False
            direct = {key: desired[key] for key in ("state", "regions") if key in desired}
            return _subset(direct, _record(world, "attire", wearer)) if direct else True
        if set(desired) - unsupported:
            out.append(_receipt("attire", wearer, check(after), check(before)))
    return out


def _overlay_receipts(before, after, changes):
    """Check each surface mark without treating its body as the mark's id."""
    from persist.commit import (
        _is_overlay_ending, _overlay_ending_handles, _overlay_handles)

    if not isinstance(changes, dict) or not changes:
        return [_unresolved("overlays", "", "missing_desired_state",
                            "A named surface mark or ending is required.")]

    def entries(world, subject):
        value = _record(world, "overlays", subject)
        if value is _MISSING:
            return []
        if value is _AMBIGUOUS:
            return None
        return value if isinstance(value, list) else [value]

    out = []
    for subject, raw in changes.items():
        desired_entries = raw if isinstance(raw, list) else [raw]
        if not desired_entries:
            out.append(_unresolved("overlays", subject, "missing_desired_state",
                                   "An empty list requests no mark or ending."))
        for index, raw_entry in enumerate(desired_entries):
            desired = _without_metadata(raw_entry)
            ending = _is_overlay_ending(desired)
            handles = (_overlay_ending_handles(desired) if ending
                       else _overlay_handles(desired))
            known_subject = _known(after, subject) or (ending and _known(before, subject))
            if not handles or not known_subject:
                out.append(_unresolved(
                    "overlays", subject, "invalid_or_missing_target",
                    "An established body and an identifiable surface mark are required.",
                    operation=index))
                continue

            def check(world):
                standing = entries(world, subject)
                if standing is None:
                    return False
                if ending:
                    # The commit matches an ending's literal text against a
                    # standing mark's handles. An unfamiliar record carrying
                    # that same text is not proof the mark disappeared either.
                    return not any(
                        handles & (_overlay_handles(item) | _overlay_ending_handles(item))
                        for item in standing)
                return any(
                    handles & _overlay_handles(item)
                    and (isinstance(desired, str) or _subset(desired, item))
                    and not _is_overlay_ending(item)
                    for item in standing)

            out.append(_receipt("overlays", subject, check(after), check(before),
                                operation=index))
    return out


def verify_patch(before, after, patch, *, item_id=None, chrono_id=None, specialist="",
                 verification_context=None):
    """Return channel/target receipts; never mutate inputs or execute a patch.

    ``before`` and ``after`` must be the adjacent worlds for THIS span, including
    domain projections such as attire. Comparing the beginning and end of a
    whole beat would incorrectly acquit intermediate changes. Each unresolved
    receipt remains outstanding even when another effect in the row succeeds.
    """
    context = patch if verification_context is None else verification_context
    receipts = []
    for channel, changes in (patch.items() if isinstance(patch, dict) else []):
        if channel in _META:
            continue
        if channel in {"entities", "positions", "stations", "poses", "containment"}:
            receipts.extend(_map_receipts(before, after, channel, changes, context))
        elif channel == "rooms":
            receipts.extend(_rooms_receipts(before, after, changes))
        elif channel == "remove_adjacent":
            receipts.extend(_adjacency_removal_receipts(before, after, changes))
        elif channel == "scales":
            receipts.extend(_scale_receipts(before, after, changes))
        elif channel == "destruction":
            receipts.extend(_destruction_receipts(before, after, changes))
        elif channel == "location":
            receipts.extend(_scalar_receipts(before, after, channel, changes))
        elif channel == "weather":
            receipts.extend(_weather_receipts(before, after, changes))
        elif channel == "time":
            receipts.extend(_time_receipts(before, after, changes))
        elif channel in {"remove_entities", "remove_rooms"}:
            receipts.extend(_removal_receipts(before, after, channel, changes))
        elif channel == "inventory_ops":
            receipts.extend(_inventory_receipts(before, after, changes, context))
        elif channel == "contact_ops":
            receipts.extend(_contact_receipts(before, after, changes))
        elif channel == "attire":
            receipts.extend(_attire_receipts(before, after, changes))
        elif channel == "overlays":
            receipts.extend(_overlay_receipts(before, after, changes))
        else:
            receipts.append(_unresolved(channel, "", "unsupported_channel",
                                        "This channel has no scene postcondition verifier."))
    if not receipts:
        receipts.append(_unresolved("", "", "missing_desired_state",
                                    "A completion claim without a typed desired effect is unverified."))
    for receipt in receipts:
        if item_id is not None:
            receipt["item_id"] = item_id
        if chrono_id is not None:
            receipt["chrono_id"] = chrono_id
        if specialist:
            receipt["specialist"] = specialist
    return receipts


def verify_causal_worlds(worlds):
    """Verify stored chronological snapshots without consulting final state."""
    receipts = []
    for span in worlds or []:
        rows = verify_patch(span.get("before") or {}, span.get("after") or {},
                            span.get("patch") or {}, item_id=span.get("item_id"),
                            chrono_id=span.get("chrono_id"), specialist=span.get("specialist", ""))
        for row in rows:
            if "stage" in span:
                row["stage"] = span["stage"]
        receipts.extend(rows)
    return deepcopy(receipts)
