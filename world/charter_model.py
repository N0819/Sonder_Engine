"""The five primitives an institution is made of. Pure data, no I/O.

``docs/design/DESIGN_INSTITUTIONS_AND_UPKEEP.md`` §3. Nothing here names a
genre: the engine knows that a number leaves a range and that a body can or
cannot service a tag. A lorebook decides whether the number is reactor coolant,
ward observations, or whether the office is sung at the hours.

THE FIVE, and the one naming trap:

  * **upkeep** -- a condition that must stay above a floor and drifts below it
    when unattended.
  * **post** -- a duty slot: a place, a competence requirement, the upkeeps it
    serves.
  * **competence** -- ``{tag: level}`` on a body. The tags are authored.
  * **watch** -- the assignment of bodies to posts for a window. Output, not
    input.
  * **charter** -- the institution: its upkeeps, its posts, the roster it
    BELIEVES it has, and its standing priority when it cannot fill everything.

A duty slot is a ``post``, never a ``station``: ``scene.stations`` already
means a body's within-room position, and a second spelling of a live word is
how this repo gets hurt.

Shapes are plain dicts with normalizers rather than dataclasses, matching
``living_world.normalize_living_world`` and ``attire.normalize_regions`` -- the
state has to survive a JSON round trip into ``world`` storage without a second
representation to keep in step.
"""

from __future__ import annotations

from .charter_chatter import normalize_window_acts
from .charter_figure import normalize_figures
from .charter_mark import normalize_marks

#: A level is a fraction of nominal: 1.0 is perfectly kept, 0.0 is gone.
LEVEL_MAX = 1.0
LEVEL_MIN = 0.0

#: What an unnamed upkeep floor defaults to. Deliberately not zero: a floor of
#: zero means "this can never fail", which is never what an author means by
#: leaving the field blank, and a silently un-failable upkeep is exactly the
#: kind of authored blank that reads as complete and is not.
DEFAULT_FLOOR = 0.25


def number(value, default=0.0):
    """A model-authored finite-looking number, or the caller's default."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def integer(value, default=0):
    """A model-authored integer, or the caller's default."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return int(default)


def _clamp(value, low=LEVEL_MIN, high=LEVEL_MAX):
    try:
        value = float(value)
    except (TypeError, ValueError):
        return low
    return max(low, min(high, value))


def _tags(value):
    """``{tag: level}``, levels as non-negative ints, unnamed tags dropped."""
    out = {}
    if not isinstance(value, dict):
        return out
    for tag, level in value.items():
        tag = str(tag or "").strip()
        if not tag:
            continue
        try:
            level = int(level)
        except (TypeError, ValueError):
            level = 1
        out[tag] = max(0, level)
    return out


#: Public spelling of the tag normalizer, for the siblings. A private name
#: reached across modules is a facade waiting to be got wrong.
normalize_competence = _tags


def _string_list(value, *, mapping_keys=False):
    """Bounded authored labels without treating scalars as iterables.

    Model-authored JSON occasionally substitutes a number or an object for a
    requested list. Numeric values carry no safe semantic authority and are
    dropped. For explicitly key-shaped fields, an object may stand for its
    keys; otherwise only strings and ordinary JSON arrays are accepted.
    """
    if isinstance(value, str):
        value = [value]
    elif isinstance(value, dict):
        value = list(value) if mapping_keys else []
    elif not isinstance(value, (list, tuple, set)):
        value = []
    return [str(item) for item in value if str(item or "").strip()]


def normalize_upkeep(key, entry):
    """One condition the institution owes.

    ``drift_per_hour`` is what neglect costs; ``service_per_hour`` is what one
    competent body restores. Both are per hour so a caller may advance any
    window without the model caring how long a turn is.
    """
    entry = entry if isinstance(entry, dict) else {}
    depends = _string_list(entry.get("depends_on"))
    return {
        "key": str(key),
        "place": str(entry.get("place") or ""),
        "level": _clamp(entry.get("level", LEVEL_MAX)),
        "floor": _clamp(entry.get("floor", DEFAULT_FLOOR)),
        "drift_per_hour": max(0.0, float(entry.get("drift_per_hour") or 0.0)),
        "service_per_hour": max(
            0.0, float(entry.get("service_per_hour") or 0.0)),
        "requires": _tags(entry.get("requires")),
        # WHAT THIS CONDITION IS MADE OUT OF. A tended post restores an
        # upkeep only as far as the things it draws on allow: a baker with a
        # full oven and no flour works at the rate the flour permits, however
        # competent and however present. Named upkeeps only, so a supply chain
        # is a graph over conditions the institution already owes rather than
        # a second kind of object.
        #
        # This is the field the town fixture demanded and the ship never
        # needed. It is also, deliberately, the only concession made to it:
        # `depends_on` plus the existing four fields is a supply chain, and no
        # goods, prices, inventories or markets were added to get one.
        "depends_on": depends,
    }


def normalize_post(key, entry):
    """One duty slot. ``serves`` names the upkeeps it tends."""
    entry = entry if isinstance(entry, dict) else {}
    serves = _string_list(entry.get("serves"))
    authority = _string_list(entry.get("authority"), mapping_keys=True)
    out = {
        "key": str(key),
        "place": str(entry.get("place") or ""),
        # Human meaning for a duty. ``serves`` remains the mechanical edge;
        # purpose lets a historian say what the work was without exposing an
        # id such as ``lead_psychologist`` as autobiography.
        "purpose": " ".join(str(entry.get("purpose") or "").split())[:500],
        "serves": serves,
        "requires": _tags(entry.get("requires")),
        # An optional authored reporting line names another POST, not a
        # person. Reassignment changes who briefs whom without rewriting
        # identity or history.
        "reports_to": str(entry.get("reports_to") or "").strip(),
        # A closed list of institutional action families this office may
        # originate.  Empty remains the common case: hierarchy can carry
        # reports without making every supervisor an autonomous executive.
        "authority": sorted({
            str(value) for value in authority
            if str(value).strip()}),
    }
    # What this post's holders visibly wear and what the work marks them
    # with, authored by the planner in the population's words
    # (`charter_surface.post_dress`). Absent when the plan wrote none: the
    # engine invents no apron for a forge it has never seen.
    from .charter_surface import post_dress
    dress = post_dress(entry)
    if dress["worn"]:
        out["worn"] = dress["worn"]
    if dress["marks"]:
        out["marks"] = dress["marks"]
    return out


def normalize_body(key, entry):
    """A person the charter may assign.

    ``available`` is GROUND TRUTH -- whether this body can in fact stand a
    post. What the charter thinks about it lives in the roster, which is a
    belief and may be wrong. Keeping the two apart is the whole of §5.
    """
    entry = entry if isinstance(entry, dict) else {}
    body = {
        "key": str(key),
        # Durable institutional id (`key`) and scene-facing identity (`name`)
        # are separate so a promotion/rename does not rewrite past claims.
        "name": str(entry.get("name") or key),
        "competence": _tags(entry.get("competence")),
        "available": bool(entry.get("available", True)),
        # Set only when NEEDS put this body down, so needs may pick it up
        # again and nothing else is undone by them.
        "stood_down": bool(entry.get("stood_down", False)),
        "place": str(entry.get("place") or ""),
        # Where this body lives, as distinct from where it stands: the room
        # it walks back to when neither posted nor on an errand. Defaults to
        # the authored starting place, and survives every window after,
        # which is what lets `place` be honest about visits.
        "berth": str(entry.get("berth") or entry.get("place") or ""),
        # The duty this person ordinarily belongs to. Planning may redeploy a
        # cross-qualified body when scarcity requires it, but equal candidates
        # should not trade professions every window. Older generated bodies
        # infer this from their ``post:...`` key at the planner boundary.
        "home_post": str(entry.get("home_post") or ""),
    }
    # An AUTHORED temperament only. The unauthored case is derived on demand
    # by `charter_temper.temperament_of` and stored nowhere, so the field is
    # absent for almost every body -- carrying five defaults per head would
    # be state that says nothing.
    if isinstance(entry.get("temperament"), dict):
        body["temperament"] = dict(entry["temperament"])
    habits = []
    for index, raw in enumerate(entry.get("private_habits") or ()):
        if isinstance(raw, str):
            raw = {"label": raw}
        if not isinstance(raw, dict):
            continue
        label = " ".join(str(raw.get("label") or raw.get("activity") or "")
                         .split())[:160]
        if not label:
            continue
        habit_id = str(raw.get("id") or f"habit_{index + 1}").strip()[:120]
        habits.append({
            "id": habit_id, "label": label,
            "activity": " ".join(str(raw.get("activity") or label).split())[:500],
            "privacy": "private",
            "cadence_hours": max(4.0, min(
                720.0, number(raw.get("cadence_hours"), 48.0))),
            "source": str(raw.get("source") or "authored")[:160],
        })
        if len(habits) >= 4:
            break
    if habits:
        body["private_habits"] = habits
    # Presentation metadata never participates in planning.  The body key is
    # identity; these fields may change how that identity is addressed without
    # rewriting watches, memories or institutional history.
    for field in ("title", "rank", "given_name", "family_name",
                  "dialogue_color", "resident_seed_id"):
        value = str(entry.get(field) or "").strip()
        if value:
            body[field] = value
    # What this body looks like, where generation dealt it or a Director
    # render settled it (`charter_surface`). Kept only when present: a body
    # from before the field existed is dealt the same surface on read
    # (`surface_of`), so storing nothing here keeps its bytes unchanged.
    from .charter_surface import surface_has_content
    if surface_has_content(entry.get("surface")):
        body["surface"] = dict(entry["surface"])
    # A walk in progress: the courier's shape (`charter_move`), carried only
    # while the body is between its origin and its target. Dropped on arrival
    # by the mover, and dropped here if it is not a route at all -- a body
    # whose record cannot be walked stands where its `place` says.
    rec = entry.get("walk")
    if isinstance(rec, dict):
        route = [str(r) for r in (rec.get("route") or ()) if str(r)]
        leg = integer(rec.get("leg"), 0)
        if len(route) > 1 and 0 <= leg < len(route) - 1 \
                and route[leg] == body["place"]:
            body["walk"] = {
                "target": str(rec.get("target") or route[-1]),
                "route": route, "leg": leg,
                "credit": max(0.0, number(rec.get("credit"), 0.0)),
                "held": bool(rec.get("held", False)),
            }
    return body


def body_of_an_authored_mind(charter, body_key, body=None):
    """Is this body an authored person's, rather than an extra the
    institution grew?

    TWO FACTS ANSWER IT AND ONLY ONE OF THEM IS GUARANTEED TO EXIST.

    A body is BOUND when ``charter["bindings"]`` holds its key -- written by
    `bind_promoted_character`, reached from `integrate_featured_resident`,
    which runs only down the ``character_histories`` route.  A body is
    RESERVED the moment `charter_generate` mints it against a
    ``featured_residents`` entry: it carries ``resident_seed_id``, the
    caller's seat token, and its ``name`` is the authored person's own.  The
    reservation is minted WITH the body; the binding is an optional later
    step some callers never take.  So an eligibility test that reads only
    ``bindings`` calls an authored person an anonymous extra, and does it
    silently.

    Measured, chat 95 (2026-08-28).  The story was generated by calling
    `generate_lived_location` with ``featured_residents=`` directly -- which
    the public API accepts, and which RETURNS bindings for the caller to
    apply rather than applying them -- so ``state["bindings"] == {}`` for all
    four registered cast members.  `background_presence_records` therefore
    derived ``"lieutenant_commander Data Data"`` (body
    ``operations_officer:featured:d3d39750b9``, ``resident_seed_id="cast:75"``)
    and ``"captain Jean-Luc Picard"`` as anonymous background people, which
    `background_react` then voiced on turns 2/5/7/11 and 15 in the same beats
    those characters' own agents ran; and `members_of` counted both bodies as
    crowd ground, 10 members on ``main_bridge`` where 8 is right.

    Identity is never tested by comparing rendered display strings.  A
    formatter stands between the stored name and the rendered one -- the same
    chat's ``formal_format`` rendered the registered character "Data" as
    "lieutenant_commander Data Data" -- so the downstream roster guards keyed
    on display-name equality could not recover what this predicate lets
    through.  Ask the body; it always knows.

    ``bindings`` is membership-tested, not indexed: the slices
    `agents.common.chatter_inputs` builds carry it as a frozenset of keys.
    """
    body_key = str(body_key)
    if body_key in ((charter or {}).get("bindings") or ()):
        return True
    if body is None:
        body = ((charter or {}).get("bodies") or {}).get(body_key) or {}
    return bool(str((body or {}).get("resident_seed_id") or "").strip())


#: How many autobiographical rows one body may carry. This was 16, chosen when
#: the only writer was beat-scale gossip in a 96-hour tail and the cost of a
#: row had not been measured. It has been: a row is ~324 bytes of JSON and
#: carries NO embedding, where a registered character's memory row costs ~718
#: bytes of text plus ~20.5 KB of vector -- Charter memory is about 65x cheaper
#: per row than the tier it feeds. At this cap a body holding a full life costs
#: well under a megabyte, against presim arithmetic that runs at ~1.8 ms per
#: simulated hour. The old number was not protecting anything that needed
#: protecting; it was throwing away the depth the promoted character is for.
EXPERIENCE_CAP = 4000


def _optional_float(value):
    """A float, or None for absent/unreadable. Booleans are not numbers."""
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def normalize_charter(stored, reservation=None):
    """A whole institution, from any shape, with its priority ordering closed.

    An upkeep absent from ``priority`` is appended in key order rather than
    dropped: a charter that silently stops caring about a condition because
    somebody forgot to rank it is the failure this repo keeps paying for in
    other subsystems.

    ``reservation`` (`charter_identity.identity_reservation`) is the story's
    registered identity forms. It is optional because normalization is
    story-agnostic -- a charter fixture, a tool run and an archive all
    normalize with no chat in reach -- and every caller that HAS a story
    passes it, so the law it stores stops offering a registered mind's
    address and the mint refuses to take one.
    """
    stored = stored if isinstance(stored, dict) else {}
    upkeeps = {
        str(k): normalize_upkeep(k, v)
        for k, v in (stored.get("upkeeps") or {}).items()}
    posts = {
        str(k): normalize_post(k, v)
        for k, v in (stored.get("posts") or {}).items()}
    from .charter_identity import (
        materialize_body_names, normalize_naming_profile, strip_reserved_pools)
    from .charter_surface import normalize_looks_profile
    naming = strip_reserved_pools(
        normalize_naming_profile(stored.get("naming")), reservation)
    raw_bodies = materialize_body_names(
        str(stored.get("key") or "charter"), stored.get("bodies") or {},
        naming, reservation)
    bodies = {
        str(k): normalize_body(k, v)
        for k, v in raw_bodies.items()}

    priority = [str(p) for p in (stored.get("priority") or [])
                if str(p) in upkeeps]
    for key in sorted(upkeeps):
        if key not in priority:
            priority.append(key)

    from .charter_commitment import normalize_commitments
    from .charter_decide import normalize_decisions
    from .charter_economy import normalize_economy
    from .charter_social import (normalize_judgments, normalize_social_norms,
                                 normalize_ties)
    from .charter_intervene import normalize_interventions
    from .charter_trigger import (normalize_pending_changes,
                                  normalize_triggers, prune_trigger_last)

    # HOISTED OUT OF THE LITERAL because `ties` is validated against them.
    # No behaviour change to either -- the literal below references these
    # locals -- but a validator cannot read a sibling entry of the dict it is
    # being built inside, and the alternative is normalizing judgments twice.
    judgments = normalize_judgments(stored.get("judgments"))
    # HOISTED for the same reason `judgments` is: `trigger_last` is pruned
    # against the longest refractory in the rule set, so the validator has to
    # read a sibling entry of the dict it is being built inside.
    triggers = normalize_triggers(stored.get("triggers"))
    served_beside = {
        str(key): {str(other): int(n) for other, n in held.items()}
        for key, held in (stored.get("served_beside") or {}).items()
        if isinstance(held, dict)}

    return {
        "key": str(stored.get("key") or "charter"),
        "upkeeps": upkeeps,
        "posts": posts,
        "bodies": bodies,
        "naming": naming,
        # The population's look law (`charter_surface`): pools per axis in
        # its own words. Empty pools mean the engine default deals.
        "looks": normalize_looks_profile(stored.get("looks")),
        "priority": priority,
        "roster": dict(stored.get("roster") or {}),
        # Last planned watch is present institutional state: it tells a scene
        # which duty this body is actually standing.  Dropping it during
        # normalization erased role continuity at every persistence boundary.
        "watch": {
            str(post): str(body)
            for post, body in (stored.get("watch") or {}).items()
            if str(post) in posts and str(body) in bodies
        },
        "clock_hours": float(stored.get("clock_hours") or 0.0),
        # Standing conditions already written down, so a fact that persists
        # across windows is reported once rather than every window. Carried on
        # the charter rather than held in a runner, because a caller that
        # checkpoints and restores must restore this too or the restored run
        # re-reports everything it had already said.
        "reported": {
            str(kind): dict(entries)
            for kind, entries in (stored.get("reported") or {}).items()
            if isinstance(entries, dict)},
        # The change frame one window deposits for the next to fire on. It
        # rides the charter for the reason `reported` above does and it is the
        # sharper case of the same rule: a caller that checkpoints and restores
        # without it drops every consequence that was in flight at the moment
        # of the save, silently and with no error anywhere. Capped here, which
        # is the enforcement point that counts.
        "pending_changes": normalize_pending_changes(
            stored.get("pending_changes")),
        # When each rule last fired for each pair. Pruned to the rule set's
        # longest refractory and hard-capped, because without the prune this
        # is rules x ordered pairs -- 32 x 10^6 on `charter_worlds.big_town`.
        "trigger_last": prune_trigger_last(
            stored.get("trigger_last"), triggers,
            stored.get("clock_hours") or 0.0),
        # The room graph the bodies stand in, in `world.spatial`'s own shape,
        # or absent for an institution small enough to be one place. Carried
        # rather than passed so a charter is a single restorable object.
        "scene": stored.get("scene") or None,
        # Optional registry-side planned location graph. The live scene is
        # composed under it by charter_runtime and never replaces it.
        "structure": str(stored.get("structure") or ""),
        # WHEN THIS INSTITUTION'S DAY BEGINS. A charter counts its own hours
        # from zero; these two say what hour of the story's day that zero was
        # and how long that day is, so `world/day_cycle.charter_phase` can
        # name the phase of any window -- and so a presimulated month and an
        # in-play catch-up read the same table. Set by `charter_runtime`
        # from the story clock (never authored), and None for an institution
        # the story has not yet told when it is, which is every charter
        # written before the cycle existed and every fixture: no anchor, no
        # phase, and the movers behave exactly as they always have.
        "day_anchor_hours": _optional_float(stored.get("day_anchor_hours")),
        "day_length_hours": _optional_float(stored.get("day_length_hours")),
        # Places a body may go FOR ITS OWN SAKE: rooms that belong to no post
        # and no upkeep and that people are in anyway. `posts` and `upkeeps`
        # between them say where the WORK is, and until this existed that was
        # the only set circulation could route to, so a room whose purpose is
        # being in it was unreachable to the whole population. Author-facing
        # and sparse; `charter_space.commons_places` reads it alongside the
        # market places the economy already carried. Empty is legal and means
        # the institution has none, which `charter_runtime.registry_warnings`
        # says out loud rather than leaving to be discovered fifty beats on.
        "commons": sorted({str(p).strip()
                           for p in (stored.get("commons") or ())
                           if str(p or "").strip()}),
        # One belief set per head, about the bodies that head has met. Held
        # beside the charter's own roster rather than replacing it: an
        # institution is an agent too, and its register is its belief, not a
        # summary of everyone else's.
        "minds": {
            str(holder): {str(s): dict(c) for s, c in claims.items()
                          if isinstance(c, dict)}
            for holder, claims in (stored.get("minds") or {}).items()
            if isinstance(claims, dict)},
        # Regard, standing and blame. Normalized by `charter_politics` at use
        # rather than here, to keep this module free of behaviour.
        "politics": dict(stored.get("politics") or {}),
        # Local, evidence-citing stances.  These do not replace `politics`:
        # regard remains the narrow credibility weight used by telling.
        "social_norms": normalize_social_norms(stored.get("social_norms")),
        # Authored consequence rules, merged over `charter_trigger`'s defaults
        # (`RESEARCH.md` §1.7.6 item 5). Merged HERE rather than at the firing
        # site for the reason `experiences` records below: `normalize_charter`
        # runs at the head of every `step`, so a rule set closed onto bounds
        # anywhere else is re-opened at the next window boundary.
        "triggers": triggers,
        "judgments": judgments,
        # The discrete tie beside the numeric axes (`RESEARCH.md` §1.7.6 item
        # 3). NORMALIZATION IS A VALIDATOR HERE, not a coercion: a label the
        # numbers no longer support is DELETED, which is what makes a tie that
        # contradicts the axes unrepresentable on every path into this state --
        # archive import, checkpoint restore of an older charter shape, a
        # hand-edited registry, and any future writer that moves a judgment
        # without calling `update_ties`. Sparse and derived, so a charter saved
        # before this existed loads with `{}` and rebuilds on its next window.
        "ties": normalize_ties(
            stored.get("ties"), bodies=bodies, judgments=judgments,
            politics=stored.get("politics"), served_beside=served_beside),
        # Locally recognised social commitments, distinct from both the
        # beat-level pending-obligations ledger and place owed-history.
        "commitments": normalize_commitments(stored.get("commitments")),
        # Aggregate lots/markets and the institution's bounded agenda/order
        # state.  Empty input remains a strict no-op for old Charters.
        "economy": normalize_economy(stored.get("economy")),
        "decisions": normalize_decisions(stored.get("decisions")),
        "interventions": normalize_interventions(stored.get("interventions")),
        "refused_interventions": [
            dict(row) for row in (stored.get("refused_interventions") or ())
            if isinstance(row, dict)][-24:],
        # Author-facing prehistory products. This is never a mind payload;
        # residents learn its facts only where presim events reached them.
        "history": dict(stored.get("history") or {}),
        # People the institution can know without owning: the player, the
        # major characters, anyone with a mind of their own elsewhere. Not
        # bodies — never rostered, never planned, never blamed, and holding
        # no mind here. See `charter_figure`.
        "figures": normalize_figures(stored.get("figures")),
        # A promoted body remains an institutional projection: Charter may
        # try to roster it, but registered-character cognition and movement
        # own the person from this point forward.
        "bindings": {
            str(key): {
                "char_id": value.get("char_id"),
                "entity_id": str(value.get("entity_id") or ""),
                "name": str(value.get("name") or key),
                "promoted_turn": value.get("promoted_turn"),
            }
            for key, value in (stored.get("bindings") or {}).items()
            if str(key) in bodies and isinstance(value, dict)
            and value.get("char_id") is not None},
        # Per-body needs, and the ground each body has covered. Needs are the
        # reason `available` can stop being an authored flag; `travelled` is a
        # diagnostic carried beside the bodies rather than on them.
        "needs": {
            str(key): {str(n): dict(spec) for n, spec in held.items()
                       if isinstance(spec, dict)}
            for key, held in (stored.get("needs") or {}).items()
            if isinstance(held, dict)},
        # How much felt state is allowed to bias the watch bill. 0.0 is the
        # default and the shipped behaviour: mood is computed, reported, and
        # read by nothing. Above zero it joins standing and pressure on the
        # reluctance axis, which is the only way in it will ever get -- an
        # experiment with a dial, not a second planner.
        "mood_weight": float(stored.get("mood_weight") or 0.0),
        # Open social situations. Sparse: a population with nothing going on
        # between it carries none. See `charter_practice`.
        # Places where social detail is simulated at beat resolution. Empty
        # is the default and means none: a body off-screen keeps its needs,
        # feeling, belief and past, and simply is not gossiping this window.
        "news_keys": sorted(
            str(k) for k in (stored.get("news_keys") or ()) if k),
        "active_places": sorted(
            str(p) for p in (stored.get("active_places") or ()) if p),
        "practices": {
            str(k): dict(v) for k, v in (stored.get("practices") or {}).items()
            if isinstance(v, dict) and v.get("kind")},
        # Body-owned pre-story experience.  Social rows are copied only to
        # their participants; private-habit rows only to the body itself.
        # Bounded per body, so history grows with meaningful intersections,
        # never with every quiet simulation window.
        #
        # THE BOUND LIVES HERE, and this is the enforcement point that counts:
        # `normalize_charter` runs at the head of every `step`, so a cap raised
        # only where the rows are WRITTEN is inert -- the next window boundary
        # truncates them again. Measured with the writer's constant already at
        # 4000: 1091 rows minted, 639 kept, 39 of 40 holders pinned at exactly
        # 16, and the losses were entirely the coarse writer's own kinds.
        "experiences": {
            str(holder): [dict(row) for row in rows
                          if isinstance(row, dict)][-EXPERIENCE_CAP:]
            for holder, rows in (stored.get("experiences") or {}).items()
            if str(holder) in bodies and isinstance(rows, list)},
        "habit_runs": {
            str(holder): {
                str(habit): float(at)
                for habit, at in runs.items()
                if str(habit)
            }
            for holder, runs in (stored.get("habit_runs") or {}).items()
            if str(holder) in bodies and isinstance(runs, dict)},
        # Who has learned they are blamed. Blame was an institutional fact
        # that reached nobody; this is the record of it having been said out
        # loud to the person it landed on.
        "heard_blame": {
            str(k): sorted(str(x) for x in v)
            for k, v in (stored.get("heard_blame") or {}).items()},
        # Per-body felt state, in `mind/psychology_runtime`'s own persisted
        # shapes -- see `charter_feel`. Sparse: a body feeling nothing has no
        # entry, so a quiet institution carries an empty dict.
        "feel": {
            str(key): dict(entry)
            for key, entry in (stored.get("feel") or {}).items()
            if isinstance(entry, dict)},
        # What full strain multiplies the rest drift by
        # (`charter_needs.advance_needs`). None means the shipped default,
        # `charter_feel.STRAIN_REST_TOLL`; carried explicitly so an
        # experiment arm can pin it, including to zero.
        "strain_toll": (None if stored.get("strain_toll") is None
                        else max(0.0, float(stored.get("strain_toll")))),
        # Chance per HOUR that an off-duty body goes somewhere
        # (`charter_move.errands`). None means the shipped default,
        # `charter_move.ERRAND_RATE`; 0.0 pins the quiet control — nobody
        # stirs, which is the pre-circulation behaviour exactly.
        "errand_rate": (None if stored.get("errand_rate") is None
                        else max(0.0, float(stored.get("errand_rate")))),
        # Windows actually stood, per body per post. Bounded by bodies x
        # posts rather than by time, and the evidence a promotion call needs
        # to deliberate a project from -- a month at the same post is a
        # life's shape, and nothing else records it.
        "stood": {
            str(key): {str(p): int(n) for p, n in held.items()}
            for key, held in (stored.get("stood") or {}).items()
            if isinstance(held, dict)},
        # Who each body stood its watches BESIDE, counted the same way. The
        # companion to `stood`: that one says what a body did with its life,
        # this one says who it did it with, and neither grows with time.
        "served_beside": served_beside,
        # Socially temporary facts -- newly raised, lately helped, accused to
        # your face, in disgrace. Bounded by bodies x `charter_mark.MARKS`
        # and pruned at expiry, so it carries the same bound `stood` and
        # `served_beside` do: it grows with the shape of the institution and
        # never with the hours. Filtered to live bodies for the same reason
        # `experiences` and `habit_runs` are -- a body that leaves the charter
        # must not leave a mark behind -- and this is the filter that counts,
        # because `normalize_charter` runs at the head of every `step`.
        "marks": normalize_marks(stored.get("marks"), bodies=bodies),
        # The last landed window's acts, room-stamped, for the ambient
        # chatter the perception layer renders
        # (DESIGN_BACKGROUND_PRESENTATION §A). Carried here because
        # `normalize_charter` rebuilds the state from this literal at every
        # persistence boundary AND at the head of every `step` — the
        # transient `acts` list dies at both, so a field only the runner
        # held would leave every saved, restored or merely re-stepped
        # charter silent. Institution-level on purpose: talk in a room is
        # the room's record, not any one person's store.
        "window_acts": normalize_window_acts(
            stored.get("window_acts"), bodies),
        "travelled": {str(k): int(v)
                      for k, v in (stored.get("travelled") or {}).items()},
        # Every edge every body has walked, ``{body: {from: {to: n}}}`` in
        # room-id vocabulary. Bounded by the graph rather than by time (a
        # crossing counts up, it does not append), and kept because it is
        # the one record a promotion can hand over as EARNED routes rather
        # than the institution's map (`charter_promote.inherited_place_graph`).
        "walked": {
            str(body): {
                str(origin): {str(end): int(n) for end, n in ends.items()
                              if int(n or 0) > 0}
                for origin, ends in (routes or {}).items()
                if isinstance(ends, dict)}
            for body, routes in (stored.get("walked") or {}).items()
            if isinstance(routes, dict) and str(body) in bodies},
    }


def meets(competence, requirement):
    """Does this competence map satisfy every tag of a requirement."""
    for tag, level in (requirement or {}).items():
        if int((competence or {}).get(tag, 0)) < int(level):
            return False
    return True


def out_of_band(upkeep):
    return float(upkeep["level"]) < float(upkeep["floor"])


def priority_rank(charter):
    """``{upkeep_key: rank}``, 0 being the thing the institution abandons last.

    The whole characterisation of an institution is this ordering -- life
    support above the galley, the office above the fire -- so it is a first
    class field and not a tie-break.
    """
    return {key: rank for rank, key in enumerate(charter["priority"])}
